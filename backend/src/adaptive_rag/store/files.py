"""The upload folder: validate files by content, then save them (FR1, FR2, FR6)."""

import hashlib
import io
import zipfile
from pathlib import Path

from adaptive_rag.config import settings

SUPPORTED_TYPES = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".html": "html",
    ".htm": "html",
    ".md": "md",
    ".markdown": "md",
    ".txt": "txt",
}


class InvalidFileError(Exception):
    """The upload is the wrong type, too big, or not what its name claims."""


def detect_file_type(filename: str, content: bytes) -> str:
    """Return pdf/docx/html/md/txt, checking the bytes, not just the extension."""
    suffix = Path(filename).suffix.lower()
    file_type = SUPPORTED_TYPES.get(suffix)
    if file_type is None:
        allowed = ", ".join(sorted(set(SUPPORTED_TYPES.values())))
        raise InvalidFileError(f"Unsupported file type '{suffix}'. Allowed: {allowed}")
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise InvalidFileError(f"File is larger than {settings.max_upload_mb} MB")
    if not content:
        raise InvalidFileError("File is empty")

    if file_type == "pdf" and not content.startswith(b"%PDF-"):
        raise InvalidFileError("File is named .pdf but is not a PDF")
    if file_type == "docx" and not _is_docx(content):
        raise InvalidFileError("File is named .docx but is not a Word document")
    if file_type in ("html", "md", "txt"):
        _require_text(content, suffix)
    return file_type


def save_upload(owner_id: str, file_type: str, content: bytes) -> tuple[str, Path]:
    """Store the file under the owner's folder, named by its hash. Returns (hash, path)."""
    file_hash = hashlib.sha256(content).hexdigest()
    folder = settings.upload_dir / owner_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{file_hash}.{file_type}"
    path.write_bytes(content)
    return file_hash, path


def delete_upload(path: str) -> None:
    Path(path).unlink(missing_ok=True)


def _is_docx(content: bytes) -> bool:
    """A .docx is a zip file containing word/document.xml."""
    if not content.startswith(b"PK\x03\x04"):
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            return "word/document.xml" in archive.namelist()
    except zipfile.BadZipFile:
        return False


def _require_text(content: bytes, suffix: str) -> None:
    """Text formats must be readable UTF-8 with no binary bytes."""
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise InvalidFileError(f"File is named {suffix} but is not UTF-8 text") from error
    if "\x00" in text:
        raise InvalidFileError(f"File is named {suffix} but contains binary data")

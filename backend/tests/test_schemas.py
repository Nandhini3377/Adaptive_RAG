import pytest
from pydantic import ValidationError

from adaptive_rag.schemas import Element


def test_element_creation():
    element = Element(type="paragraph", text="This is a sample paragraph.", page=1)
    assert element.type == "paragraph"
    assert element.text == "This is a sample paragraph."
    assert element.page == 1


def test_element_defaults():
    element = Element(type="paragraph", text="Hello")
    assert element.page is None
    assert element.section == ""


def test_element_rejects_unknown_type():
    with pytest.raises(ValidationError):
        Element(type="unknown", text="Invalid type")

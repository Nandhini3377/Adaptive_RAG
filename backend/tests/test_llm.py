"""Tests for the Sarvam LLM client.

Most tests use a fake server (httpx.MockTransport): offline, free, repeatable.
The live test calls the real API; run it with: RUN_LIVE_LLM=1 pytest -m live
"""

import json
import os

import httpx
import pytest
from pydantic import SecretStr

from adaptive_rag.llm.base import LLMError
from adaptive_rag.llm.sarvam import SarvamLLM


def fake_sarvam(content, finish_reason="stop", status=200, seen=None):
    """An HTTP client whose 'server' returns a canned chat completion."""

    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(json.loads(request.content))
        if status != 200:
            return httpx.Response(status, json={"error": {"message": "boom"}})
        return httpx.Response(
            200,
            json={
                "id": "x",
                "object": "chat.completion",
                "created": 0,
                "model": "sarvam-105b",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": finish_reason,
                    }
                ],
                "usage": {
                    "prompt_tokens": 1000,
                    "completion_tokens": 500,
                    "total_tokens": 1500,
                    "completion_tokens_details": {"reasoning_tokens": 400},
                },
            },
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    """Tests never depend on a real key being present."""
    monkeypatch.setattr(
        "adaptive_rag.llm.sarvam.settings.sarvam_api_key", SecretStr("test-key")
    )
    monkeypatch.setattr("adaptive_rag.llm.sarvam.settings.llm_max_retries", 0)


def test_complete_returns_text_tokens_and_cost():
    """Plain answers come back stripped, with usage and rupee cost."""
    llm = SarvamLLM(http_client=fake_sarvam("\nhello"))
    response = llm.complete([{"role": "user", "content": "hi"}])
    assert response.text == "hello"
    assert response.input_tokens == 1000
    assert response.output_tokens == 500
    assert response.reasoning_tokens == 400
    # 1000 * 29.28 / 1M + 500 * 73.20 / 1M
    assert response.cost_inr == pytest.approx(0.06588)


def test_request_sends_model_caps_and_effort():
    """Every call caps tokens and sets reasoning effort (both cost money)."""
    seen = []
    llm = SarvamLLM(http_client=fake_sarvam("ok", seen=seen))
    llm.complete([{"role": "user", "content": "hi"}], max_tokens=200)
    assert seen[0]["model"] == "sarvam-105b"
    assert seen[0]["max_tokens"] == 200
    assert seen[0]["reasoning_effort"] == "low"
    assert "response_format" not in seen[0]


def test_complete_json_sends_schema_and_parses_data():
    """Structured calls send the JSON schema and return parsed data."""
    seen = []
    schema = {"type": "object", "properties": {"city": {"type": "string"}}}
    llm = SarvamLLM(http_client=fake_sarvam('{"city": "Paris"}', seen=seen))
    response = llm.complete_json(
        [{"role": "user", "content": "?"}], schema, name="capital"
    )
    assert response.data == {"city": "Paris"}
    sent_format = seen[0]["response_format"]
    assert sent_format["type"] == "json_schema"
    assert sent_format["json_schema"]["name"] == "capital"
    assert sent_format["json_schema"]["schema"] == schema


def test_complete_json_rejects_non_json():
    """If the model ignores the schema, we fail clearly instead of guessing."""
    llm = SarvamLLM(http_client=fake_sarvam("Paris, I think"))
    with pytest.raises(LLMError, match="Expected JSON"):
        llm.complete_json([{"role": "user", "content": "?"}], {"type": "object"})


def test_running_out_of_tokens_is_a_clear_error():
    """A reasoning model that spends the budget thinking returns nothing."""
    llm = SarvamLLM(http_client=fake_sarvam("", finish_reason="length"))
    with pytest.raises(LLMError, match="Ran out of tokens"):
        llm.complete([{"role": "user", "content": "hi"}], max_tokens=50)


def test_api_errors_become_llm_errors():
    """Provider errors are wrapped so callers handle one error type."""
    llm = SarvamLLM(http_client=fake_sarvam("", status=403))
    with pytest.raises(LLMError, match="Sarvam call failed"):
        llm.complete([{"role": "user", "content": "hi"}])


def test_missing_key_fails_at_startup(monkeypatch):
    """No key gives a clear message, not a confusing 403 later."""
    monkeypatch.setattr(
        "adaptive_rag.llm.sarvam.settings.sarvam_api_key", SecretStr("")
    )
    with pytest.raises(LLMError, match="SARVAM_API_KEY"):
        SarvamLLM()


@pytest.mark.live
@pytest.mark.skipif(
    not os.getenv("RUN_LIVE_LLM"), reason="set RUN_LIVE_LLM=1 to call Sarvam"
)
def test_live_sarvam_plain_and_json(monkeypatch):
    """One real round trip: plain text and schema-shaped JSON."""
    monkeypatch.undo()  # use the real key from .env
    llm = SarvamLLM()
    plain = llm.complete(
        [{"role": "user", "content": "Reply with just the word: hello"}]
    )
    assert "hello" in plain.text.lower()
    schema = {
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
        "additionalProperties": False,
    }
    structured = llm.complete_json(
        [{"role": "user", "content": "What is the capital of France?"}], schema
    )
    assert structured.data == {"city": "Paris"}

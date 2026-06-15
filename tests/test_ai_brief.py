import os

from src.compute.ai_brief import (
    build_chatgpt_payload,
    extract_response_text,
    has_openai_key,
)


def test_has_openai_key_reads_environment(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert not has_openai_key()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert has_openai_key()


def test_build_chatgpt_payload_uses_grounded_context():
    payload = build_chatgpt_payload("信息技术 +1.8亿，扩散72%")

    assert payload["model"]
    assert "不要编造" in payload["input"]
    assert "信息技术 +1.8亿" in payload["input"]


def test_extract_response_text_supports_responses_api_shape():
    payload = {
        "output": [
            {
                "content": [
                    {"type": "output_text", "text": "先看信息技术，注意金融对冲。"}
                ]
            }
        ]
    }

    assert extract_response_text(payload) == "先看信息技术，注意金融对冲。"

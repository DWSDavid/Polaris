import os
from pathlib import Path

from src.ai.brief import (
    build_deepseek_payload,
    build_chatgpt_payload,
    extract_chat_completion_text,
    extract_response_text,
    generate_ai_brief,
    has_ai_key,
    has_openai_key,
)


def test_has_openai_key_reads_environment(monkeypatch):
    assert not Path("src/compute/ai_brief.py").exists()
    monkeypatch.setattr("src.ai.brief.load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert not has_openai_key()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert has_openai_key()


def test_has_ai_key_reads_selected_provider_environment(monkeypatch):
    monkeypatch.setattr("src.ai.brief.load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    assert not has_ai_key("deepseek")

    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-test")
    assert has_ai_key("deepseek")


def test_build_chatgpt_payload_uses_grounded_context():
    payload = build_chatgpt_payload("信息技术 +1.8亿，扩散72%")

    assert payload["model"]
    assert "不要编造" in payload["input"]
    assert "信息技术 +1.8亿" in payload["input"]


def test_build_deepseek_payload_uses_openai_compatible_chat_shape(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)

    payload = build_deepseek_payload("银行 主力流入2.1亿，扩散65%")

    assert payload["model"] == "deepseek-v4-flash"
    assert payload["stream"] is False
    assert payload["thinking"] == {"type": "disabled"}
    assert payload["messages"][0]["role"] == "system"
    assert "不要编造" in payload["messages"][0]["content"]
    assert payload["messages"][1]["role"] == "user"
    assert "银行 主力流入2.1亿" in payload["messages"][1]["content"]


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


def test_extract_chat_completion_text_supports_deepseek_shape():
    payload = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "电子扩散强，先跟踪龙头成交量。",
                }
            }
        ]
    }

    assert extract_chat_completion_text(payload) == "电子扩散强，先跟踪龙头成交量。"


def test_generate_ai_brief_posts_to_deepseek_chat_completions(monkeypatch):
    calls = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {"message": {"content": "先看通信和电子，金融不要对冲。"}}
                ]
            }

    def fake_post(url, headers, json, timeout):
        calls.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        return Response()

    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-test")
    monkeypatch.setattr("src.ai.brief.requests.post", fake_post)

    result = generate_ai_brief("通信 +2.3%，扩散80%", provider="deepseek", timeout=7)

    assert result == "先看通信和电子，金融不要对冲。"
    assert calls[0]["url"] == "https://api.deepseek.com/chat/completions"
    assert calls[0]["headers"]["Authorization"] == "Bearer ds-test"
    assert calls[0]["json"]["model"] == "deepseek-v4-flash"
    assert "通信 +2.3%" in calls[0]["json"]["messages"][1]["content"]
    assert calls[0]["timeout"] == 7

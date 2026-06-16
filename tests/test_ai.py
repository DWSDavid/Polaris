from unittest.mock import patch

from src.ai.ai_client import chat
from src.ai.summarize import build_sector_prompt, summarize_sector


def test_prompt_only_contains_given_numbers():
    facts = {
        "sector": "电力设备",
        "state": "主升扩散",
        "trend_days": 9,
        "inflow_10d": 12.3,
        "diffusion": 0.72,
        "top_leaders": "阳光电源、宁德时代",
    }

    prompt = build_sector_prompt(facts)

    assert "电力设备" in prompt and "9" in prompt and "12.3" in prompt
    assert "不要编造" in prompt or "禁止" in prompt
    assert "阳光电源、宁德时代" in prompt


def test_summarize_parses_response():
    with patch("src.ai.ai_client.chat", return_value="电力设备主升扩散，已持续9天。"):
        out = summarize_sector(
            {
                "sector": "电力设备",
                "state": "主升扩散",
                "trend_days": 9,
                "inflow_10d": 12.3,
                "diffusion": 0.72,
                "top_leaders": "阳光电源",
            }
        )

    assert "电力设备" in out


def test_chat_returns_placeholder_without_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert "未配置 AI API Key" in chat([{"role": "user", "content": "hello"}])


def test_chat_posts_to_deepseek_compatible_endpoint(monkeypatch):
    calls = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "只基于真实数值总结。"}}]}

    def fake_post(url, headers, json, timeout):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return Response()

    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-test")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("src.ai.ai_client.requests.post", fake_post)

    result = chat([{"role": "user", "content": "电力设备 9 12.3"}], timeout=7)

    assert result == "只基于真实数值总结。"
    assert calls[0]["url"] == "https://api.deepseek.com/chat/completions"
    assert calls[0]["headers"]["Authorization"] == "Bearer ds-test"
    assert calls[0]["json"]["model"] == "deepseek-v4-flash"
    assert calls[0]["timeout"] == 7

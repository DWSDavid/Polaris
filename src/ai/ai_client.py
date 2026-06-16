"""OpenAI-compatible AI client with DeepSeek as the default provider."""

from __future__ import annotations

import os

import requests
from dotenv import load_dotenv

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
NO_KEY_PLACEHOLDER = "未配置 AI API Key；当前只展示 Polaris 本地计算出的真实数值。"


def chat(
    messages: list[dict],
    api_key: str | None = None,
    model: str | None = None,
    timeout: int = 30,
) -> str:
    load_dotenv()
    provider = _select_provider(api_key)
    key = api_key or _provider_key(provider)
    if not key:
        return NO_KEY_PLACEHOLDER

    response = requests.post(
        _provider_url(provider),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        json=_payload(provider, messages, model=model),
        timeout=timeout,
    )
    response.raise_for_status()
    return _extract_chat_text(response.json())


def _select_provider(api_key: str | None = None) -> str:
    if api_key or os.getenv("DEEPSEEK_API_KEY"):
        return "deepseek"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return "deepseek"


def _provider_key(provider: str) -> str | None:
    if provider == "openai":
        return os.getenv("OPENAI_API_KEY")
    return os.getenv("DEEPSEEK_API_KEY")


def _provider_url(provider: str) -> str:
    if provider == "openai":
        return OPENAI_URL
    return DEEPSEEK_URL


def _payload(provider: str, messages: list[dict], model: str | None = None) -> dict:
    default_model = (
        os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
        if provider == "openai"
        else os.getenv("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL)
    )
    payload = {
        "model": model or default_model,
        "messages": messages,
        "stream": False,
        "temperature": 0.2,
    }
    if provider == "deepseek":
        payload["thinking"] = {"type": os.getenv("DEEPSEEK_THINKING", "disabled")}
    return payload


def _extract_chat_text(payload: dict) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""
    return str(choices[0].get("message", {}).get("content") or "").strip()

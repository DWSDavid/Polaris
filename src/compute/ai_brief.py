"""Optional AI brief generation for grounded market context."""

from __future__ import annotations

import os

import requests
from dotenv import load_dotenv

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEEPSEEK_CHAT_COMPLETIONS_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"

SYSTEM_PROMPT = (
    "你是A股板块轮动和组合风险分析助手。只使用用户给出的结构化数据，"
    "不要编造行情、新闻、财务数据或未出现的股票。"
)
USER_PROMPT_TEMPLATE = (
    "{context}\n\n"
    "请用中文输出：1. 大趋势；2. 资金和分化；3. 龙头联动；"
    "4. 成长/老经济对冲风险；5. 今天该怎么观察。"
)


def has_openai_key() -> bool:
    load_dotenv()
    return bool(os.getenv("OPENAI_API_KEY"))


def has_ai_key(provider: str | None = None) -> bool:
    load_dotenv()
    selected = _normalize_provider(provider)
    env_name = "DEEPSEEK_API_KEY" if selected == "deepseek" else "OPENAI_API_KEY"
    return bool(os.getenv(env_name))


def build_chatgpt_payload(context: str, model: str | None = None) -> dict:
    return {
        "model": model or os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        "input": f"{SYSTEM_PROMPT}\n\n{USER_PROMPT_TEMPLATE.format(context=context)}",
    }


def build_deepseek_payload(context: str, model: str | None = None) -> dict:
    thinking_type = os.getenv("DEEPSEEK_THINKING", "disabled").strip().lower()
    if thinking_type not in {"enabled", "disabled"}:
        thinking_type = "disabled"

    payload = {
        "model": model or os.getenv("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_PROMPT_TEMPLATE.format(context=context),
            },
        ],
        "thinking": {"type": thinking_type},
        "stream": False,
        "temperature": 0.2,
    }
    if thinking_type == "enabled":
        payload["reasoning_effort"] = os.getenv("DEEPSEEK_REASONING_EFFORT", "high")
    return payload


def generate_chatgpt_brief(
    context: str,
    api_key: str | None = None,
    model: str | None = None,
    timeout: int = 30,
) -> str:
    return generate_ai_brief(
        context,
        provider="openai",
        api_key=api_key,
        model=model,
        timeout=timeout,
    )


def generate_ai_brief(
    context: str,
    provider: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    timeout: int = 30,
) -> str:
    load_dotenv()
    selected = _normalize_provider(provider)
    if selected == "deepseek":
        return _generate_deepseek_brief(context, api_key=api_key, model=model, timeout=timeout)

    return _generate_openai_brief(context, api_key=api_key, model=model, timeout=timeout)


def _generate_openai_brief(
    context: str,
    api_key: str | None = None,
    model: str | None = None,
    timeout: int = 30,
) -> str:
    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        return "未设置 OPENAI_API_KEY。当前展示本地规则分析，设置环境变量后可生成 ChatGPT 总结。"

    response = requests.post(
        OPENAI_RESPONSES_URL,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        json=build_chatgpt_payload(context, model=model),
        timeout=timeout,
    )
    response.raise_for_status()
    return extract_response_text(response.json())


def _generate_deepseek_brief(
    context: str,
    api_key: str | None = None,
    model: str | None = None,
    timeout: int = 30,
) -> str:
    key = api_key or os.getenv("DEEPSEEK_API_KEY")
    if not key:
        return "未设置 DEEPSEEK_API_KEY。当前展示本地规则分析，设置环境变量后可生成 DeepSeek 总结。"

    response = requests.post(
        DEEPSEEK_CHAT_COMPLETIONS_URL,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        json=build_deepseek_payload(context, model=model),
        timeout=timeout,
    )
    response.raise_for_status()
    return extract_chat_completion_text(response.json())


def extract_response_text(payload: dict) -> str:
    if payload.get("output_text"):
        return str(payload["output_text"])
    chunks = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                chunks.append(str(text))
    return "\n".join(chunks).strip()


def extract_chat_completion_text(payload: dict) -> str:
    choices = payload.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {})
    return str(message.get("content") or "").strip()


def _normalize_provider(provider: str | None = None) -> str:
    selected = (provider or os.getenv("AI_PROVIDER", "deepseek")).strip().lower()
    if selected in {"chatgpt", "gpt", "openai"}:
        return "openai"
    return "deepseek"

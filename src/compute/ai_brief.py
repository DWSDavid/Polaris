"""Optional OpenAI brief generation for grounded market context."""

from __future__ import annotations

import os

import requests
from dotenv import load_dotenv

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-4.1-mini"


def has_openai_key() -> bool:
    load_dotenv()
    return bool(os.getenv("OPENAI_API_KEY"))


def build_chatgpt_payload(context: str, model: str | None = None) -> dict:
    return {
        "model": model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
        "input": (
            "你是A股板块轮动和组合风险分析助手。只使用下面给出的数据，"
            "不要编造行情、新闻或财务数据。\n\n"
            f"{context}\n\n"
            "请用中文输出：1. 大趋势；2. 资金和分化；3. 龙头联动；"
            "4. 成长/老经济对冲风险；5. 今天该怎么观察。"
        ),
    }


def generate_chatgpt_brief(
    context: str,
    api_key: str | None = None,
    model: str | None = None,
    timeout: int = 30,
) -> str:
    load_dotenv()
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

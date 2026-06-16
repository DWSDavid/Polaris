"""Grounded AI summary for style/regime research."""

from __future__ import annotations

from src.ai import ai_client

SYSTEM_PROMPT = (
    "你是A股风格与风口研究助手。只使用传入 facts，不要编造指数、利率、资金、政策或行业名。"
    "输出只是研究辅助，人最后决定，不自动下单。"
)

USER_PROMPT = (
    "请用中文分点输出：1. 近1年总结；2. 近3年总结；"
    "3. 各次风格转换及其可能原因，必须围绕利率/流动性/政策/盈利四类线索；"
    "4. 当前处于什么风格、风口在哪；5. 风险与验证。"
    "只使用传入 facts，若 facts 没有原因字段，就说证据不足，不要编造。"
)


def build_regime_prompt(facts: dict) -> str:
    lines = [
        USER_PROMPT,
        "安全约束：只使用传入 facts；不要编造任何未给出的宏观、政策、盈利或行业信息。",
        "facts:",
    ]
    lines.extend(_flatten(facts))
    return "\n".join(lines)


def regime_brief(facts: dict, timeout: int = 30) -> str:
    return ai_client.chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_regime_prompt(facts)},
        ],
        timeout=timeout,
    )


def _flatten(value, prefix: str = "") -> list[str]:
    lines = []
    if isinstance(value, dict):
        for key, item in value.items():
            name = f"{prefix}.{key}" if prefix else str(key)
            lines.extend(_flatten(item, name))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            name = f"{prefix}[{index}]"
            lines.extend(_flatten(item, name))
        if not value:
            lines.append(f"- {prefix}: []")
    else:
        lines.append(f"- {prefix}: {value}")
    return lines

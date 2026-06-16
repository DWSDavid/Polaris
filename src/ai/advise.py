"""Grounded portfolio-level decision briefs."""

from __future__ import annotations

from src.ai import ai_client

SYSTEM_PROMPT = (
    "你是A股中期波段决策辅助。只能使用用户提供的结构化事实，"
    "不要编造价格、资金、个股名、新闻或财务数据。人最后决定，你不自动下单。"
)

SECTION_PROMPT = (
    "请用中文分点输出 5 点以内："
    "1. 大趋势；2. 资金与分化；3. 龙头联动；"
    "4. 持仓、对冲与担保比；5. 今日观察。"
    "每一点必须引用下面 facts 中已有字段，不要补充未给出的数字。"
)


def build_advice_prompt(facts: dict) -> str:
    lines = [
        SECTION_PROMPT,
        "安全约束：不要编造任何未给出的行情/资金/个股/新闻，不给买卖指令。",
        "facts:",
    ]
    lines.extend(_flatten_facts(facts))
    return "\n".join(lines)


def advise(facts: dict) -> str:
    return ai_client.chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_advice_prompt(facts)},
        ]
    )


def _flatten_facts(value, prefix: str = "") -> list[str]:
    lines = []
    if isinstance(value, dict):
        for key, item in value.items():
            name = f"{prefix}.{key}" if prefix else str(key)
            lines.extend(_flatten_facts(item, name))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            name = f"{prefix}[{index}]"
            lines.extend(_flatten_facts(item, name))
        if not value:
            lines.append(f"- {prefix}: []")
    else:
        lines.append(f"- {prefix}: {value}")
    return lines

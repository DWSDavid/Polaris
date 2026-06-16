from unittest.mock import patch

from src.ai.regime_brief import build_regime_prompt, regime_brief


def test_build_regime_prompt_contains_style_theme_macro_and_constraints():
    facts = {
        "one_year": {"summary": "小盘占优后切大盘"},
        "three_year": {"summary": "成长到价值再到资源"},
        "epochs": [
            {
                "start": "2025-01",
                "end": "2025-06",
                "regime": "小盘占优",
                "themes": [{"sector": "电子", "avg_strength": 3.2}],
                "macro": {"cn_10y": 2.1, "northbound_net": 20.0, "margin_balance": 18000.0},
            }
        ],
        "current": {"style": "大盘占优", "themes": ["钨", "稀土"]},
    }

    prompt = build_regime_prompt(facts)

    for keyword in ["近1年总结", "近3年总结", "风格转换", "利率", "流动性", "政策", "盈利", "当前处于什么风格"]:
        assert keyword in prompt
    for keyword in ["epochs", "macro", "cn_10y", "northbound_net", "margin_balance", "电子", "钨"]:
        assert keyword in prompt
    assert "只使用传入 facts" in prompt
    assert "不要编造" in prompt


def test_regime_brief_uses_chat_client():
    with patch("src.ai.ai_client.chat", return_value="1. 近1年总结：大盘占优。"):
        out = regime_brief({"current": {"style": "大盘占优"}})

    assert "大盘占优" in out

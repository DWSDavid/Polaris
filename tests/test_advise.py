from unittest.mock import patch

from src.ai.advise import advise, build_advice_prompt


def test_prompt_has_sections_and_only_given_facts():
    facts = {
        "mainline": "证券",
        "mainline_trend_days": 6,
        "mainline_inflow_10d": 30.0,
        "holdings": [{"name": "华泰证券", "sector": "证券", "state": "主升扩散"}],
        "candidates": ["证券", "电子"],
        "hedge_pairs": [["证券", "电子"]],
        "guarantee_ratio": 1.69,
    }

    prompt = build_advice_prompt(facts)

    for keyword in ["大趋势", "资金", "对冲", "持仓", "观察"]:
        assert keyword in prompt
    assert "证券" in prompt
    assert "华泰证券" in prompt
    assert "不要编造" in prompt


def test_prompt_adds_readable_fact_summary_for_model():
    facts = {
        "mainline": "证券",
        "mainline_trend_days": 6,
        "mainline_inflow_10d": 30.0,
        "holdings": [{"name": "华泰证券", "sector": "证券", "state": "主升扩散"}],
        "candidates": ["证券", "电子"],
        "hedge_pairs": [["证券", "电子"]],
        "guarantee_ratio": 1.69,
        "today_watch": "观察证券是否继续扩散，电子是否造成组合对冲。",
    }

    prompt = build_advice_prompt(facts)

    assert "当前主线: 证券, 持续6天, 10日资金30.0" in prompt
    assert "当前持仓: 华泰证券(证券, 主升扩散)" in prompt
    assert "候选篮子: 证券、电子" in prompt
    assert "对冲对: 证券↔电子" in prompt
    assert "今日观察: 观察证券是否继续扩散，电子是否造成组合对冲。" in prompt


def test_prompt_adds_thicker_decision_facts_for_model():
    facts = {
        "mainline": "证券",
        "mainline_trend_days": 8,
        "mainline_inflow_10d": 30.0,
        "historical_analogy": {"sample_count": 12, "median_remaining_positive_days": 5},
        "rotation_flow": {"rotation_label": "资金接力流入", "net_inflow": 2.4},
        "valuation_guard": {"level": "watch", "message": "估值偏高"},
        "hedge_score": 0.62,
        "hedge_pairs": [["证券", "电子"]],
        "guarantee_ratio": 1.69,
        "trend_days": 8,
        "leader_linkage": {"label": "龙头确认"},
    }

    prompt = build_advice_prompt(facts)

    for keyword in ["周期判断", "资金与分化", "龙头联动", "对冲与担保比", "今日观察"]:
        assert keyword in prompt
    for keyword in ["历史类比", "资金接力", "估值护栏", "对冲度", "趋势持续", "龙头确认"]:
        assert keyword in prompt
    assert "80-220" in prompt


def test_advise_parses():
    with patch("src.ai.ai_client.chat", return_value="1. 大趋势：证券仍是观察主线。"):
        out = advise(
            {
                "mainline": "证券",
                "holdings": [],
                "candidates": [],
                "hedge_pairs": [],
                "guarantee_ratio": 1.69,
            }
        )

    assert "证券" in out

from unittest.mock import patch

from src.ai.humanize import assert_no_jargon
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

    assert "当前主线：证券" in prompt
    assert "主线持续：6天" in prompt
    assert "主线10日资金：+30.0亿" in prompt
    assert "当前持仓：华泰证券，证券，主升扩散" in prompt
    assert "候选篮子：证券、电子" in prompt
    assert "对冲对：证券↔电子" in prompt
    assert "今日观察：观察证券是否继续扩散，电子是否造成组合对冲。" in prompt


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


def test_prompt_includes_cycle_ignition_and_market_context_for_model():
    facts = {
        "mainline": "证券",
        "cycle": {"position_in_box": 0.86, "midterm_trend": 1, "cum_inflow_20d": 5e8},
        "ignition": {"ignition_flag": True, "ignition_score": 0.72},
        "market_context": {
            "northbound": "北向资金平稳",
            "dragon_tiger": "龙虎榜活跃",
            "research": "研报维持增持",
            "news": "新闻提到非银资金流入",
        },
    }

    prompt = build_advice_prompt(facts)

    for keyword in ["周期阶段", "中期结构是否完好", "箱体位置", "多周资金", "启动迹象"]:
        assert keyword in prompt
    for keyword in ["北向", "龙虎榜", "研报", "新闻"]:
        assert keyword in prompt
    assert "position_in_box" not in prompt
    assert "ignition_flag" not in prompt


def test_prompt_forbids_false_missing_when_fact_is_present():
    prompt = build_advice_prompt(
        {
            "rotation_flow": {"rotation_label": "资金接力流入", "net_inflow": 2.4},
            "leader_linkage": {"label": "龙头确认"},
            "today_watch": "观察证券扩散是否延续。",
        }
    )

    assert "禁止把已经出现的事实说成缺失" in prompt
    assert "资金接力流入" in prompt
    assert "龙头确认" in prompt
    assert "观察证券扩散是否延续" in prompt


def test_prompt_includes_ranked_investment_directions_for_model():
    prompt = build_advice_prompt(
        {
            "ranked_directions": [
                {
                    "sector": "电子",
                    "score": 4.2,
                    "reasons": ["中期趋势向上", "20日资金+24.0亿"],
                },
                {
                    "sector": "银行",
                    "score": -1.1,
                    "reasons": ["拐点预警", "估值分位90%"],
                },
            ],
            "avoid_directions": ["银行"],
        }
    )

    assert "综合方向排序" in prompt
    assert "电子，综合分4.20" in prompt
    assert "score=4.2" not in prompt
    assert "回避方向：银行" in prompt


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


def test_advise_falls_back_when_model_returns_jargon():
    with patch("src.ai.ai_client.chat", return_value="ranked_directions[0].score=4.2"):
        out = advise(
            {
                "ranked_directions": [
                    {
                        "sector": "电子",
                        "score": 4.2,
                        "reasons": ["中期趋势向上"],
                    }
                ],
                "today_watch": "观察电子扩散是否延续。",
            }
        )

    assert "电子" in out
    assert "结论" in out
    assert_no_jargon(out)

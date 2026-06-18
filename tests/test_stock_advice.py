from unittest.mock import patch

from src.ai.humanize import assert_no_jargon
from src.ai.stock_advice import build_stock_advice_prompt, stock_advice


def _facts():
    return {
        "name": "华泰证券",
        "code": "601688",
        "sector": "证券",
        "sector_state": "主升扩散",
        "latest_price": 19.7,
        "pct_chg": 2.4,
        "above_ma20": True,
        "above_ma60": True,
        "stock_inflow_5d": 200_000_000,
        "sector_inflow_10d": 3_000_000_000,
        "position_in_box": 0.72,
        "decision": {
            "stance": "适合观察入场",
            "score": 6.2,
            "reasons": ["行业主线支持", "个股中期结构向上"],
            "risk_flags": [],
        },
    }


def test_stock_prompt_uses_trading_agent_style_roles_without_raw_field_names():
    prompt = build_stock_advice_prompt(_facts())

    for keyword in ["结论", "技术面", "资金面", "行业背景", "风控", "真实事实"]:
        assert keyword in prompt
    assert "华泰证券" in prompt
    assert "stock_inflow_5d" not in prompt
    assert "position_in_box" not in prompt
    assert "不要编造" in prompt


def test_stock_advice_falls_back_when_model_returns_jargon():
    with patch("src.ai.ai_client.chat", return_value="decision.score=6.2"):
        out = stock_advice(_facts())

    assert "华泰证券" in out
    assert "适合观察入场" in out
    assert_no_jargon(out)

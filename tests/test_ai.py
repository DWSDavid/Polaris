from unittest.mock import patch

from src.ai.ai_client import chat
from src.ai.humanize import assert_no_jargon
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


def test_sector_prompt_includes_thicker_decision_facts():
    facts = {
        "sector": "证券",
        "state": "主升扩散",
        "trend_days": 8,
        "historical_analogy": {"sample_count": 12, "median_remaining_positive_days": 5},
        "rotation_flow": {"rotation_label": "资金接力流入", "net_inflow": 2.4},
        "valuation_guard": {"level": "watch", "message": "估值偏高"},
        "hedge_score": 0.62,
        "leader_linkage": {"label": "龙头确认"},
    }

    prompt = build_sector_prompt(facts)

    for keyword in ["周期判断", "资金与分化", "龙头联动", "对冲与担保比", "今日观察"]:
        assert keyword in prompt
    for keyword in ["历史类比", "资金接力", "估值护栏", "对冲度", "龙头联动"]:
        assert keyword in prompt
    for keyword in ["historical_analogy", "rotation_flow", "valuation_guard", "hedge_score", "leader_linkage"]:
        assert keyword not in prompt
    assert "80-220" in prompt


def test_sector_prompt_guides_cycle_ignition_and_context_judgment():
    facts = {
        "sector": "证券",
        "cycle": {"position_in_box": 0.86, "midterm_trend": 1, "cum_inflow_20d": 5e8},
        "ignition": {"ignition_flag": True, "ignition_score": 0.72},
        "market_context": {
            "northbound": "北向资金平稳",
            "dragon_tiger": "龙虎榜活跃",
            "research": "研报维持增持",
            "news": "新闻提到非银资金流入",
        },
    }

    prompt = build_sector_prompt(facts)

    for keyword in ["周期阶段", "中期结构是否完好", "箱体位置", "多周资金", "启动迹象"]:
        assert keyword in prompt
    for keyword in ["北向", "龙虎榜", "研报", "新闻"]:
        assert keyword in prompt
    assert "position_in_box" not in prompt
    assert "ignition_flag" not in prompt


def test_sector_prompt_is_humanized_and_conclusion_first():
    prompt = build_sector_prompt(
        {
            "sector": "原材料",
            "position_in_box": 1.0,
            "ignition_flag": True,
            "inflow_10d": 30e8,
        }
    )

    assert "结论" in prompt
    assert "箱体位置：顶部" in prompt
    assert "启动迹象：已出现" in prompt
    assert "10日主力资金：+30.0亿" in prompt
    assert "position_in_box" not in prompt
    assert "ignition_flag" not in prompt


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


def test_summarize_falls_back_when_model_returns_jargon():
    with patch("src.ai.ai_client.chat", return_value="position_in_box=1.0，score=4.2"):
        out = summarize_sector(
            {
                "sector": "原材料",
                "state": "主升扩散",
                "position_in_box": 1.0,
                "inflow_10d": 30e8,
                "top_leaders": "厦门钨业",
            }
        )

    assert "原材料" in out
    assert "箱体位置" in out
    assert_no_jargon(out)


def test_chat_returns_placeholder_without_key(monkeypatch):
    monkeypatch.setattr("src.ai.ai_client.load_dotenv", lambda *args, **kwargs: None)
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

    monkeypatch.setattr("src.ai.ai_client.load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-test")
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("src.ai.ai_client.requests.post", fake_post)

    result = chat([{"role": "user", "content": "电力设备 9 12.3"}], timeout=7)

    assert result == "只基于真实数值总结。"
    assert calls[0]["url"] == "https://api.deepseek.com/chat/completions"
    assert calls[0]["headers"]["Authorization"] == "Bearer ds-test"
    assert calls[0]["json"]["model"] == "deepseek-v4-flash"
    assert calls[0]["timeout"] == 7

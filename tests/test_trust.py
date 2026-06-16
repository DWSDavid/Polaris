from src.compute.trust import TRUST_DISCLAIMER, trust_badge, with_disclaimer


def test_trust_badge_marks_thin_samples_and_timestamp():
    badge = trust_badge({"stock_count": 8}, as_of="2026-06-16 14:30")

    assert badge["data_time"] == "2026-06-16 14:30"
    assert badge["sample_label"] == "样本少，谨慎"
    assert badge["oos_label"] == "暂无样本外校准"
    assert "成分股 8" in badge["summary"]
    assert "样本少，谨慎" in badge["summary"]


def test_trust_badge_reports_oos_win_rate_when_present():
    badge = trust_badge(
        {"stock_count": 64, "historical_win_rate": 0.62},
        as_of="2026-06-16 14:30",
    )

    assert badge["sample_label"] == "样本充足"
    assert badge["oos_label"] == "样本外胜率 62%"


def test_with_disclaimer_appends_once():
    text = with_disclaimer("结论：先观察电子。")

    assert text.endswith(TRUST_DISCLAIMER)
    assert with_disclaimer(text).count(TRUST_DISCLAIMER) == 1

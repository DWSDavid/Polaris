from __future__ import annotations

from src.pipeline.direction_history import (
    build_direction_snapshot,
    load_direction_history,
    save_direction_snapshot,
)


def test_build_direction_snapshot_keeps_only_actionable_top_directions():
    ranked = [
        {"sector": "综合", "score": 9.0, "reasons": ["太大"]},
        {"sector": "电子", "score": 7.0, "reasons": ["20日资金+3.0亿"]},
        {"sector": "其他", "score": 6.0, "reasons": ["不可解释"]},
        {"sector": "金融", "score": 5.0, "reasons": ["趋势持续4天"]},
    ]

    snapshot = build_direction_snapshot(ranked, as_of="2026-06-18 15:02")

    assert snapshot["date"] == "2026-06-18"
    assert [item["sector"] for item in snapshot["top_directions"]] == ["电子", "金融"]
    assert "综合" not in snapshot["summary"]


def test_save_and_load_direction_history_round_trips(tmp_path, monkeypatch):
    from src.pipeline import direction_history as dh

    monkeypatch.setattr(dh, "HISTORY_DIR", tmp_path)
    snapshot = build_direction_snapshot(
        [{"sector": "电子", "score": 7.0, "reasons": ["20日资金+3.0亿"]}],
        as_of="2026-06-18 15:02",
    )

    path = save_direction_snapshot(snapshot)
    loaded = load_direction_history(limit=1)

    assert path.exists()
    assert loaded[0]["date"] == "2026-06-18"
    assert loaded[0]["top_directions"][0]["sector"] == "电子"

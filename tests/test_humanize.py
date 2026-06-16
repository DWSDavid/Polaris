import pytest

from src.ai.humanize import assert_no_jargon, humanize_facts


def test_humanize_maps_to_chinese_labels_and_units():
    text = "\n".join(
        humanize_facts(
            {
                "sector": "原材料",
                "position_in_box": 1.0,
                "ignition_flag": True,
                "inflow_10d": 30e8,
                "score": 4.2,
            }
        )
    )

    assert "行业：原材料" in text
    assert "箱体位置：顶部" in text
    assert "启动迹象：已出现" in text
    assert "10日主力资金：+30.0亿" in text
    assert "综合分：4.20" in text
    assert "position_in_box" not in text
    assert "ignition_flag" not in text
    assert "score=" not in text


def test_humanize_ranked_directions_without_variable_names():
    text = "\n".join(
        humanize_facts(
            {
                "ranked_directions": [
                    {
                        "sector": "电子",
                        "score": 4.2,
                        "reasons": ["中期趋势向上", "20日资金+24.0亿"],
                        "children": ["其他电子Ⅲ", "消费电子"],
                    }
                ],
                "avoid_directions": ["银行"],
            }
        )
    )

    assert "方向排序" in text
    assert "电子" in text
    assert "综合分4.20" in text
    assert "细分含其他电子Ⅲ、消费电子" in text
    assert "回避方向：银行" in text
    assert_no_jargon(text)


def test_assert_no_jargon_rejects_variable_names_and_equals():
    with pytest.raises(ValueError):
        assert_no_jargon("position_in_box=1.0，score=4.2")

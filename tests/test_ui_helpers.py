import plotly.graph_objects as go

from src.app import ui


def test_state_badge_uses_known_state_color_and_escapes_text():
    badge = ui.state_badge("主升扩散<script>")

    assert ui.STATE_COLORS["主升扩散"] in badge
    assert "主升扩散&lt;script&gt;" in badge
    assert "<script>" not in badge


def test_state_badge_unknown_state_uses_neutral_color():
    badge = ui.state_badge("未知状态")

    assert ui.NEUTRAL_STATE_COLOR in badge
    assert "未知状态" in badge


def test_plotly_template_applies_dark_workbench_defaults():
    fig = go.Figure()

    got = ui.plotly_template(fig)

    assert got is fig
    assert fig.layout.paper_bgcolor == "rgba(0,0,0,0)"
    assert fig.layout.plot_bgcolor == "rgba(0,0,0,0)"
    assert fig.layout.font.color == ui.INK_COLOR
    assert fig.layout.margin.t == 24

import py_compile
from pathlib import Path


def test_streamlit_pages_exist_and_compile():
    paths = [
        Path("src/app/ui.py"),
        Path("src/app/Home.py"),
        Path("src/app/pages/1_板块轮动排名.py"),
        Path("src/app/pages/2_风险驾驶舱.py"),
        Path("src/app/pages/3_个股观察.py"),
        Path("src/app/pages/4_龙头联动分析.py"),
        Path("src/app/pages/5_历史联动验证.py"),
    ]
    for path in paths:
        assert path.exists()
        py_compile.compile(str(path), doraise=True)


def test_stock_pages_use_stock_panel():
    home = Path("src/app/Home.py").read_text(encoding="utf-8")
    ranking = Path("src/app/pages/1_板块轮动排名.py").read_text(encoding="utf-8")
    stock_page = Path("src/app/pages/3_个股观察.py").read_text(encoding="utf-8")
    assert "apply_theme" in home
    assert "format_percent" in ranking
    assert "get_stock_panel" in ranking
    assert "stock_panel" in stock_page
    assert "pct_chg" in ranking
    assert "latest_close" in stock_page
    assert "volume_ratio" in stock_page
    assert "stock_role" in stock_page
    assert "action_hint" in ranking


def test_home_uses_market_intelligence_workbench():
    home = Path("src/app/Home.py").read_text(encoding="utf-8")
    ui = Path("src/app/ui.py").read_text(encoding="utf-8")

    assert "build_sector_panel_v2" in home
    assert "summarize_sector" in home
    assert "em_client.industry_realtime" in home
    assert "main_net_inflow" in home
    assert "inflow_10d" in home
    assert "主线候选表" in home
    assert "行情未接入" in home
    assert "AI 总结" in home
    assert "_render_market_treemap" in home
    assert "_render_candidate_table" in home
    assert "ttl=600" in home
    assert "st.code(" not in home
    assert "polaris-hero" in ui
    assert "--polaris-bg: #10130f" in ui


def test_home_ui_helper_import_contract():
    from src.app.ui import apply_theme, hero, metric_grid, note, status_line

    assert callable(apply_theme)
    assert callable(hero)
    assert callable(metric_grid)
    assert callable(note)
    assert callable(status_line)


def test_streamlit_theme_uses_dark_workbench_defaults():
    config = Path(".streamlit/config.toml")
    assert config.exists()
    text = config.read_text(encoding="utf-8")
    assert 'base = "dark"' in text
    assert 'backgroundColor = "#10130f"' in text


def test_env_example_documents_deepseek_defaults():
    text = Path(".env.example").read_text(encoding="utf-8")
    assert "AI_PROVIDER=deepseek" in text
    assert "DEEPSEEK_API_KEY=" in text
    assert "DEEPSEEK_MODEL=deepseek-v4-flash" in text


def test_v2_pages_reference_linkage_stats():
    linkage = Path("src/app/pages/4_龙头联动分析.py").read_text(encoding="utf-8")
    history = Path("src/app/pages/5_历史联动验证.py").read_text(encoding="utf-8")
    assert "linkage_stats" in linkage
    assert "detect_leader_events" in history
    assert "summarize_linkage_stats" in history


def test_risk_page_references_portfolio_offset():
    risk_page = Path("src/app/pages/2_风险驾驶舱.py").read_text(encoding="utf-8")
    assert "build_portfolio_exposure" in risk_page
    assert "portfolio_offset_report" in risk_page
    assert "sector_diagnostics" in risk_page

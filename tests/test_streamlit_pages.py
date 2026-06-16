import py_compile
from pathlib import Path


def test_streamlit_pages_exist_and_compile():
    paths = [
        Path("src/app/ui.py"),
        Path("src/app/Home.py"),
        Path("src/app/pages/0_使用说明.py"),
        Path("src/app/pages/1_行业下钻.py"),
        Path("src/app/pages/2_风险驾驶舱.py"),
    ]
    for path in paths:
        assert path.exists()
        py_compile.compile(str(path), doraise=True)


def test_streamlit_navigation_only_contains_v2_pages():
    pages_dir = Path("src/app/pages")
    page_names = {path.name for path in pages_dir.glob("*.py")}

    assert "0_使用说明.py" in page_names
    assert "1_行业下钻.py" in page_names
    assert "2_风险驾驶舱.py" in page_names
    assert "1_板块轮动排名.py" not in page_names
    assert "3_个股观察.py" not in page_names
    assert "4_龙头联动分析.py" not in page_names
    assert "5_历史联动验证.py" not in page_names


def test_usage_guide_explains_core_workflow_and_terms():
    guide = Path("src/app/pages/0_使用说明.py").read_text(encoding="utf-8")

    assert "explain_term" in guide
    assert "冷启动" in guide
    assert "主升扩散" in guide
    assert "龙头孤立" in guide
    assert "行业下钻" in guide
    assert "风险驾驶舱" in guide


def test_home_uses_market_intelligence_workbench():
    home = Path("src/app/Home.py").read_text(encoding="utf-8")
    ui = Path("src/app/ui.py").read_text(encoding="utf-8")

    assert "build_sector_panel_v2" in home
    assert "build_universe" in home
    assert "leaders=leaders" in home
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


def test_industry_drilldown_page_uses_v2_grounded_sources():
    page = Path("src/app/pages/1_行业下钻.py").read_text(encoding="utf-8")

    assert "industry_fund_flow_hist" in page
    assert "industry_cons" in page
    assert "build_universe" in page
    assert "leaders=leaders" in page
    assert "summarize_sector" in page
    assert "explain_term" in page
    assert "trend_days" in page
    assert "turning_point" in page
    assert "st.expander" in page
    assert "st.code(" not in page


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


def test_risk_page_references_portfolio_offset():
    risk_page = Path("src/app/pages/2_风险驾驶舱.py").read_text(encoding="utf-8")
    assert "build_portfolio_exposure" in risk_page
    assert "portfolio_offset_report" in risk_page
    assert "build_sector_panel_v2" in risk_page
    assert "summarize_sector" in risk_page
    assert "refresh_eod" not in risk_page
    assert "market_intelligence" not in risk_page

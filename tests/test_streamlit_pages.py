import py_compile
import importlib.util
from pathlib import Path

import pandas as pd


def test_streamlit_pages_exist_and_compile():
    paths = [
        Path("src/app/ui.py"),
        Path("src/app/Home.py"),
        Path("src/app/pages/0_使用说明.py"),
        Path("src/app/pages/1_行业下钻.py"),
        Path("src/app/pages/2_风险驾驶舱.py"),
        Path("src/app/pages/3_决策驾驶舱.py"),
        Path("src/app/pages/4_板块轮动历史.py"),
        Path("src/app/pages/5_投资方向.py"),
        Path("src/app/pages/6_风格风口研究.py"),
        Path("src/app/pages/7_个股分析.py"),
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
    assert "3_决策驾驶舱.py" in page_names
    assert "4_板块轮动历史.py" in page_names
    assert "5_投资方向.py" in page_names
    assert "6_风格风口研究.py" in page_names
    assert "7_个股分析.py" in page_names
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
    assert "aggregate_to_groups" in home
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
    assert "build_hot_dragon_focus" in home
    assert "em_context.hot_rank" in home
    assert "_hot_focus_histories" in home
    assert "akshare_client.daily_hist" in home
    assert "consecutive_up_days" in home
    assert "_render_hot_dragon_focus" in home
    assert "ttl=600" in home
    assert "st.code(" not in home
    assert "polaris-hero" in ui
    assert "--polaris-bg: #0E1117" in ui


def test_existing_pages_apply_v23_design_language():
    page_paths = [
        Path("src/app/Home.py"),
        Path("src/app/pages/1_行业下钻.py"),
        Path("src/app/pages/2_风险驾驶舱.py"),
        Path("src/app/pages/3_决策驾驶舱.py"),
    ]

    for path in page_paths:
        text = path.read_text(encoding="utf-8")
        assert "section(" in text
        if "plotly.express" in text or "plotly.graph_objects" in text:
            assert "plotly_template" in text
        assert "st.code(" not in text

    home = Path("src/app/Home.py").read_text(encoding="utf-8")
    drilldown = Path("src/app/pages/1_行业下钻.py").read_text(encoding="utf-8")

    assert "state_badge" in home
    assert "state_badge" in drilldown


def test_home_ui_helper_import_contract():
    from src.app.ui import (
        apply_theme,
        card,
        hero,
        metric_grid,
        note,
        page_intro,
        plotly_template,
        section,
        state_badge,
        status_line,
    )

    assert callable(apply_theme)
    assert callable(hero)
    assert callable(metric_grid)
    assert callable(note)
    assert callable(page_intro)
    assert callable(status_line)
    assert callable(state_badge)
    assert callable(card)
    assert callable(section)
    assert callable(plotly_template)


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


def test_all_pages_surface_a_plain_language_page_intro():
    paths = [
        Path("src/app/Home.py"),
        Path("src/app/pages/0_使用说明.py"),
        Path("src/app/pages/1_行业下钻.py"),
        Path("src/app/pages/2_风险驾驶舱.py"),
        Path("src/app/pages/3_决策驾驶舱.py"),
        Path("src/app/pages/4_板块轮动历史.py"),
        Path("src/app/pages/5_投资方向.py"),
        Path("src/app/pages/6_风格风口研究.py"),
        Path("src/app/pages/7_个股分析.py"),
    ]

    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "page_intro(" in text
        assert "这页回答" in text
        assert "怎么用" in text

    guide = Path("src/app/pages/0_使用说明.py").read_text(encoding="utf-8")
    assert "箱体位置" in guide
    assert "对冲度" in guide


def test_industry_drilldown_page_exposes_v22_advanced_signals():
    page = Path("src/app/pages/1_行业下钻.py").read_text(encoding="utf-8")

    assert "build_analogy_samples" in page
    assert "analogy_report" in page
    assert "summarize_flow_rotation" in page
    assert "build_rotation_chain" in page
    assert "leader_linkage_report" in page
    assert "turning_point_score" in page
    assert "valuation_guard" in page


def test_rotation_history_page_uses_timeline_visuals():
    page = Path("src/app/pages/4_板块轮动历史.py").read_text(encoding="utf-8")

    assert "fetch_rotation_timeline" in page
    assert "aggregate_timeline_to_groups" in page
    assert "filter_rotation_groups" in page
    assert "week_label" in page
    assert "categoryarray" in page
    assert "select_rotation_sectors" in page
    assert "heatmap_flow_matrix" in page
    assert "relative_flow_heatmap_matrix" in page
    assert "相对接力" in page
    assert "_render_leader_context" in page
    assert "综合" in page
    assert "大类说明" in page
    assert "这页回答" in page
    assert "weekly_rank" in page
    assert "leader_changes" in page
    assert "plotly_template" in page
    assert "px.line" in page
    assert "px.imshow" in page
    assert "summarize_sector_track" in page
    assert "st.code(" not in page


def test_investment_direction_page_connects_synthesis_context_and_ai():
    page = Path("src/app/pages/5_投资方向.py").read_text(encoding="utf-8")

    assert "rank_directions" in page
    assert "aggregate_to_groups" in page
    assert "filter_actionable_groups" in page
    assert "save_direction_snapshot" in page
    assert "历史记录" in page
    assert "trust_badge" in page
    assert "TRUST_DISCLAIMER" in page
    assert "凭据强度" in page
    assert "direction_score" in page
    assert "advise" in page
    assert "em_context" in page
    assert "northbound_flow" in page
    assert "dragon_tiger" in page
    assert "research_reports" in page
    assert "stock_news" in page
    assert "st.code(" not in page


def test_industry_drilldown_has_group_then_fine_sector_picker():
    page = Path("src/app/pages/1_行业下钻.py").read_text(encoding="utf-8")

    assert "map_to_group" in page
    assert "选择大类" in page
    assert "选择细分行业" in page


def test_regime_research_page_connects_regime_engine_and_ai():
    page = Path("src/app/pages/6_风格风口研究.py").read_text(encoding="utf-8")

    assert "style_spread" in page
    assert "detect_epochs" in page
    assert "dominant_theme" in page
    assert "macro_context" in page
    assert "regime_brief" in page
    assert "plotly_template" in page
    assert "st.code(" not in page


def test_stock_analysis_page_connects_stock_context_decision_and_ai():
    page = Path("src/app/pages/7_个股分析.py").read_text(encoding="utf-8")

    assert "build_stock_analysis_payload" in page
    assert "evaluate_stock_setup" in page
    assert "stock_advice" in page
    assert "技术面" in page
    assert "资金面" in page
    assert "历史陷阱" in page
    assert "行业背景" in page
    assert "TradingAgents-style" in page
    assert "st.code(" not in page
    assert "st.warning(risk) if" not in page


def test_industry_drilldown_rotation_table_formats_each_flow_column_once():
    page = _load_page_module("1_行业下钻.py")
    table = pd.DataFrame(
        {
            "sector": ["电子"],
            "flow_2d": [3e8],
            "latest_flow": [2e8],
            "flow_delta": [1e8],
        }
    )

    formatted = page._format_rotation_table(table)

    assert formatted.loc[0, "flow_2d"] == "+3.00 亿"
    assert formatted.loc[0, "latest_flow"] == "+2.00 亿"
    assert formatted.loc[0, "flow_delta"] == "+1.00 亿"


def test_streamlit_theme_uses_dark_workbench_defaults():
    config = Path(".streamlit/config.toml")
    assert config.exists()
    text = config.read_text(encoding="utf-8")
    assert 'base = "dark"' in text
    assert 'backgroundColor = "#0E1117"' in text


def test_env_example_documents_deepseek_defaults():
    text = Path(".env.example").read_text(encoding="utf-8")
    assert "AI_PROVIDER=deepseek" in text
    assert "DEEPSEEK_API_KEY=" in text
    assert "DEEPSEEK_MODEL=deepseek-v4-flash" in text


def test_risk_page_references_portfolio_offset():
    risk_page = Path("src/app/pages/2_风险驾驶舱.py").read_text(encoding="utf-8")
    assert "build_portfolio_exposure" in risk_page
    assert "portfolio_offset_report" in risk_page
    assert "exit_flag" in risk_page
    assert "build_sector_panel_v2" in risk_page
    assert "summarize_sector" in risk_page
    assert "refresh_eod" not in risk_page
    assert "market_intelligence" not in risk_page


def test_decision_cockpit_uses_basket_engine():
    page = Path("src/app/pages/3_决策驾驶舱.py").read_text(encoding="utf-8")

    assert "evaluate_basket" in page
    assert "hedge_score" in page
    assert "exit_flag" in page
    assert "portfolio_offset_report" not in page


def _load_page_module(filename: str):
    path = Path("src/app/pages") / filename
    spec = importlib.util.spec_from_file_location("streamlit_page_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

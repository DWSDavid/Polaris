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


def test_v2_pages_reference_linkage_stats():
    linkage = Path("src/app/pages/4_龙头联动分析.py").read_text(encoding="utf-8")
    history = Path("src/app/pages/5_历史联动验证.py").read_text(encoding="utf-8")
    assert "linkage_stats" in linkage
    assert "detect_leader_events" in history
    assert "summarize_linkage_stats" in history

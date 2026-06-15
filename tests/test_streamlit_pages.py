import py_compile
from pathlib import Path


def test_streamlit_pages_exist_and_compile():
    paths = [
        Path("src/app/Home.py"),
        Path("src/app/pages/1_板块轮动排名.py"),
        Path("src/app/pages/2_风险驾驶舱.py"),
        Path("src/app/pages/3_个股观察.py"),
    ]
    for path in paths:
        assert path.exists()
        py_compile.compile(str(path), doraise=True)


def test_stock_pages_use_stock_panel():
    ranking = Path("src/app/pages/1_板块轮动排名.py").read_text(encoding="utf-8")
    stock_page = Path("src/app/pages/3_个股观察.py").read_text(encoding="utf-8")
    assert "get_stock_panel" in ranking
    assert "stock_panel" in stock_page

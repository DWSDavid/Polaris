import py_compile
from pathlib import Path


def test_streamlit_pages_exist_and_compile():
    paths = [
        Path("src/app/Home.py"),
        Path("src/app/pages/1_板块轮动排名.py"),
        Path("src/app/pages/2_风险驾驶舱.py"),
    ]
    for path in paths:
        assert path.exists()
        py_compile.compile(str(path), doraise=True)

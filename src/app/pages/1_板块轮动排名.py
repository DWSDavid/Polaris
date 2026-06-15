import streamlit as st

from src.app.Home import get_panel


st.set_page_config(page_title="板块轮动排名", layout="wide")
st.title("板块轮动排名")

panel = get_panel().sort_values("strength", ascending=False)
st.dataframe(
    panel[
        [
            "strength",
            "strength_rank",
            "diffusion",
            "fund_flow",
            "leader_contrib",
            "state",
        ]
    ],
    width="stretch",
)
st.caption("输出的是状态识别，不是买卖信号。决策由人做。")

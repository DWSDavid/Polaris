from __future__ import annotations

import pandas as pd
import streamlit as st

from src.app.ui import apply_theme, hero, status_line
from src.compute.glossary import TERMS, explain_term


def render_page() -> None:
    st.set_page_config(page_title="Polaris 使用说明", layout="wide")
    apply_theme()

    status_line("v2.0 工作台：先看主线，再下钻行业，最后检查持仓风险。")
    hero(
        "Polaris 怎么用",
        "这不是自动下单工具。它把东财实时行业、资金流、趋势天数和龙头股池整理成一个中期波段观察面板，人最后决定。",
        "使用说明 / 概念解释",
    )

    st.subheader("每天的阅读顺序")
    st.markdown(
        """
        1. 先看首页大盘云图：颜色看涨跌，面积看成交额，候选表看资金和趋势持续天数。
        2. 进入行业下钻：确认行业 1-3 周趋势、每日主力净流入、龙头是否还在带队。
        3. 打开风险驾驶舱：检查自己的持仓有没有行业对冲、担保比和拐点风险。
        4. AI 总结只读系统算出的真实数值，用来解释和提醒，不作为买卖指令。
        """
    )

    st.subheader("核心概念")
    terms = ["冷启动", "主升扩散", "龙头孤立", "高位加速", "分歧退潮", "低位修复", "主力分化", "拐点", "对冲度"]
    for term in terms:
        with st.expander(term):
            st.write(explain_term(term))

    st.subheader("当前页面分工")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "page": "首页",
                    "use": "找今日主线、看大盘云图、读候选行业表。",
                },
                {
                    "page": "行业下钻",
                    "use": "看行业中期趋势、资金 track 和双龙头候选。",
                },
                {
                    "page": "风险驾驶舱",
                    "use": "把持仓、融资和行业状态放在一起看，避免行业对冲或担保比风险。",
                },
            ]
        ),
        width="stretch",
        height=160,
    )

    with st.expander("全部术语"):
        st.dataframe(
            pd.DataFrame(
                [{"term": term, "explain": explain_term(term)} for term in TERMS]
            ),
            width="stretch",
            height=320,
        )


if __name__ == "__main__":
    render_page()

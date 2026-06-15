import plotly.express as px
import streamlit as st

from src.pipeline.refresh import refresh_eod


@st.cache_data(ttl=600)
def get_panel():
    return refresh_eod()


def render_home():
    st.set_page_config(page_title="Polaris 北极星", layout="wide")
    st.title("Polaris 北极星 · 大盘云图")

    panel = get_panel()
    fig = px.treemap(
        panel.reset_index(names="sector"),
        path=["sector"],
        values="volume_amp",
        color="strength",
        color_continuous_scale="RdYlGn",
        custom_data=["state"],
    )
    fig.update_traces(texttemplate="%{label}<br>%{customdata[0]}")
    st.plotly_chart(fig, width="stretch")


if __name__ == "__main__":
    render_home()

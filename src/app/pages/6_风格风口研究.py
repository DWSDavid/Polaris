from __future__ import annotations

from datetime import datetime, timedelta

import akshare as ak
import pandas as pd
import plotly.express as px
import streamlit as st

from src.ai.regime_brief import regime_brief
from src.app.ui import apply_theme, hero, metric_grid, page_intro, plotly_template, section, status_line
from src.pipeline.rotation_timeline import fetch_rotation_timeline
from src.research.regime import detect_epochs, dominant_theme, macro_context, style_spread

DEFENSIVE_HINTS = ("银行", "证券", "保险", "煤炭", "电力", "公用", "石油")
GROWTH_HINTS = ("电子", "半导体", "通信", "计算机", "电池", "新能源", "设备")


@st.cache_data(ttl=3600)
def get_regime_payload() -> dict:
    timeline = fetch_rotation_timeline(days=260, max_sectors=28)
    spread = _style_spread(timeline)
    epochs = detect_epochs(spread)
    enriched_epochs = _attach_themes_and_macro(epochs, timeline)
    facts = _facts(spread, enriched_epochs)
    return {"timeline": timeline, "spread": spread, "epochs": enriched_epochs, "facts": facts}


def render_page() -> None:
    st.set_page_config(page_title="Polaris 风格风口研究", layout="wide")
    apply_theme()
    page_intro(
        "这页回答：市场更偏大盘防守还是小盘成长，风口在什么大类之间切换。",
        "怎么用：先看当前风格，再看风格时间线和风口段落；宏观佐证只作解释线索，缺证据就不脑补。",
    )

    try:
        payload = get_regime_payload()
        load_error = None
    except Exception as exc:
        payload = {"timeline": pd.DataFrame(), "spread": pd.Series(dtype=float), "epochs": [], "facts": {}}
        load_error = exc

    if payload["spread"].empty:
        status_line("风格研究暂不可用")
        if load_error:
            st.error(f"风格研究失败：{load_error}")
        hero("风格风口研究", "当前缺少可用风格或板块历史样本。不要用空图做判断。", "1-3年风格 / 风口 / 宏观")
        return

    ai_text = _safe_regime_brief(payload["facts"])
    current = payload["facts"].get("current", {})
    status_line("风格代理 + 板块轮动 + AKShare 宏观 · 小时级缓存 · 人最后决定")
    hero(
        "风格风口研究",
        ai_text,
        "近1年 / 近3年 / 风格转换原因",
    )
    metric_grid(
        [
            ("当前风格", str(current.get("style", "未知"))),
            ("当前风口", "、".join(current.get("themes", [])[:3]) or "-"),
            ("风格段数", str(len(payload["epochs"]))),
            ("最新spread", f"{float(payload['spread'].iloc[-1]):+.2%}"),
        ]
    )

    timeline_tab, themes_tab, macro_tab = st.tabs(["风格时间线", "风口段落", "宏观佐证"])
    with timeline_tab:
        _render_spread(payload["spread"])
    with themes_tab:
        _render_epochs(payload["epochs"])
    with macro_tab:
        _render_macro(payload["epochs"])


def _style_spread(timeline: pd.DataFrame) -> pd.Series:
    proxy = _proxy_spread_from_timeline(timeline)
    if not proxy.empty:
        return proxy
    return _try_index_spread()


def _try_index_spread() -> pd.Series:
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=365 * 3)).strftime("%Y%m%d")
    try:
        big = ak.stock_zh_index_daily_em(symbol="sh000300", start_date=start, end_date=end)
        small = ak.stock_zh_index_daily_em(symbol="sz399852", start_date=start, end_date=end)
    except Exception:
        return pd.Series(dtype=float)
    if big.empty or small.empty or "close" not in big.columns or "close" not in small.columns:
        return pd.Series(dtype=float)
    big_series = _close_series(big)
    small_series = _close_series(small)
    joined = pd.concat([big_series, small_series], axis=1, join="inner").dropna()
    if joined.empty:
        return pd.Series(dtype=float)
    return style_spread(joined.iloc[:, 0], joined.iloc[:, 1])


def _proxy_spread_from_timeline(timeline: pd.DataFrame) -> pd.Series:
    if timeline.empty:
        return pd.Series(dtype=float)
    frame = timeline.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["pct_chg"] = pd.to_numeric(frame["pct_chg"], errors="coerce").fillna(0.0)
    frame["bucket"] = frame["sector"].map(_style_bucket)
    grouped = frame.groupby(["date", "bucket"])["pct_chg"].mean().unstack()
    defensive = grouped.get("defensive")
    growth = grouped.get("growth")
    if defensive is None or growth is None:
        ranked = frame.groupby("date")["pct_chg"].mean()
        return style_spread((1 + ranked.fillna(0) / 100).cumprod(), pd.Series(1.0, index=ranked.index))
    left = (1 + defensive.fillna(0) / 100).cumprod()
    right = (1 + growth.fillna(0) / 100).cumprod()
    return style_spread(left, right)


def _attach_themes_and_macro(epochs: list[dict], timeline: pd.DataFrame) -> list[dict]:
    macro = _macro_context_for_epochs(epochs)
    enriched = []
    for epoch in epochs:
        item = dict(epoch)
        item["themes"] = dominant_theme(timeline, epoch, top_n=3)
        item["macro"] = _macro_summary(epoch, macro)
        enriched.append(item)
    return enriched


def _macro_context_for_epochs(epochs: list[dict]) -> pd.DataFrame:
    if not epochs:
        return pd.DataFrame()
    try:
        return macro_context(str(epochs[0]["start"])[:10], str(epochs[-1]["end"])[:10])
    except Exception:
        return pd.DataFrame()


def _macro_summary(epoch: dict, context: pd.DataFrame) -> dict:
    if context.empty:
        return {"rows": 0}
    start = pd.to_datetime(str(epoch["start"])[:10], errors="coerce")
    end = pd.to_datetime(str(epoch["end"])[:10], errors="coerce")
    if pd.isna(start) or pd.isna(end):
        return {"rows": 0}
    sliced = context[(context["date"] >= start) & (context["date"] <= end)]
    if sliced.empty:
        return {"rows": 0}
    return {
        "rows": int(len(sliced)),
        "cn_10y": _last_number(sliced, "cn_10y"),
        "northbound_net": _sum_number(sliced, "northbound_net"),
        "margin_balance": _last_number(sliced, "margin_balance"),
    }


def _facts(spread: pd.Series, epochs: list[dict]) -> dict:
    one_year = spread.tail(52)
    current_style = "大盘占优" if float(spread.iloc[-1]) >= 0 else "小盘占优"
    current_themes = [
        str(item.get("sector"))
        for item in (epochs[-1].get("themes", []) if epochs else [])
        if item.get("sector")
    ]
    return {
        "one_year": {
            "summary": f"近似spread从{one_year.iloc[0]:+.2%}到{one_year.iloc[-1]:+.2%}" if len(one_year) else "",
        },
        "three_year": {
            "summary": f"全窗口spread从{spread.iloc[0]:+.2%}到{spread.iloc[-1]:+.2%}",
        },
        "epochs": epochs[-8:],
        "current": {"style": current_style, "themes": current_themes},
    }


def _render_spread(spread: pd.Series) -> None:
    section("风格时间线", "spread>0 代表大盘/防守代理占优，spread<0 代表小盘/成长代理占优。")
    chart = spread.rename("spread").reset_index()
    chart.columns = ["date", "spread"]
    fig = px.line(chart, x="date", y="spread", markers=False)
    plotly_template(fig)
    fig.update_layout(height=440)
    st.plotly_chart(fig, width="stretch")


def _render_epochs(epochs: list[dict]) -> None:
    section("风口段落", "每段风格里按平均强度和资金找领涨方向。")
    rows = []
    for epoch in epochs:
        rows.append(
            {
                "开始": epoch["start"],
                "结束": epoch["end"],
                "风格": epoch["regime"],
                "风口": "、".join(str(item.get("sector")) for item in epoch.get("themes", [])[:3]),
                "spread变化": f"{epoch.get('start_value', 0):+.2%} → {epoch.get('end_value', 0):+.2%}",
            }
        )
    st.dataframe(pd.DataFrame(rows), width="stretch", height=420)


def _render_macro(epochs: list[dict]) -> None:
    section("宏观佐证", "10Y、北向、两融只作为解释线索，缺值不补。")
    rows = []
    for epoch in epochs:
        macro = epoch.get("macro", {})
        rows.append(
            {
                "开始": epoch["start"],
                "结束": epoch["end"],
                "风格": epoch["regime"],
                "10Y": macro.get("cn_10y"),
                "北向净买": macro.get("northbound_net"),
                "两融余额": macro.get("margin_balance"),
                "宏观样本": macro.get("rows"),
            }
        )
    st.dataframe(pd.DataFrame(rows), width="stretch", height=420)


def _safe_regime_brief(facts: dict) -> str:
    try:
        text = regime_brief(facts, timeout=8)
    except Exception:
        return _local_brief(facts)
    if text.startswith("未配置 AI API Key"):
        return _local_brief(facts)
    return text or _local_brief(facts)


def _local_brief(facts: dict) -> str:
    current = facts.get("current", {})
    return (
        f"1. 近1年总结：{facts.get('one_year', {}).get('summary', '样本不足')}。"
        f"2. 近3年总结：{facts.get('three_year', {}).get('summary', '样本不足')}。"
        "3. 风格转换原因：当前只看到价格、资金和宏观代理，政策/盈利证据不足，不编造。"
        f"4. 当前处于{current.get('style', '未知')}，风口在{'、'.join(current.get('themes', [])[:3]) or '未知'}。"
        "5. 继续用利率、北向、两融和板块扩散验证。"
    )


def _close_series(frame: pd.DataFrame) -> pd.Series:
    date_col = "date" if "date" in frame.columns else "日期"
    close_col = "close" if "close" in frame.columns else "收盘"
    out = pd.Series(pd.to_numeric(frame[close_col], errors="coerce").values, index=pd.to_datetime(frame[date_col], errors="coerce"))
    return out.dropna()


def _style_bucket(sector: str) -> str:
    text = str(sector)
    if any(item in text for item in DEFENSIVE_HINTS):
        return "defensive"
    if any(item in text for item in GROWTH_HINTS):
        return "growth"
    return "growth"


def _last_number(frame: pd.DataFrame, column: str):
    if column not in frame.columns:
        return None
    values = pd.to_numeric(frame[column], errors="coerce").dropna()
    return float(values.iloc[-1]) if not values.empty else None


def _sum_number(frame: pd.DataFrame, column: str):
    if column not in frame.columns:
        return None
    values = pd.to_numeric(frame[column], errors="coerce").dropna()
    return float(values.sum()) if not values.empty else None


if __name__ == "__main__":
    render_page()

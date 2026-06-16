"""Streamlit UI helpers for the Polaris decision workbench."""

from __future__ import annotations

import html
import re

import pandas as pd
import streamlit as st

INK_COLOR = "#E6EDF3"
MUTED_COLOR = "#8B949E"
SURFACE_COLOR = "#161B22"
PANEL_COLOR = "#0E1117"
LINE_COLOR = "#30363D"
ACCENT_COLOR = "#3DDC97"
NEUTRAL_STATE_COLOR = "#8B949E"

STATE_COLORS = {
    "主升扩散": "#3DDC97",
    "低位修复": "#4C9AFF",
    "冷启动": "#8B949E",
    "龙头孤立": "#E3B341",
    "高位加速": "#F0883E",
    "分歧退潮": "#F85149",
}


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
          --polaris-bg: #0E1117;
          --polaris-surface: #161B22;
          --polaris-panel: #21262D;
          --polaris-panel-2: #0B0F14;
          --polaris-ink: #E6EDF3;
          --polaris-muted: #8B949E;
          --polaris-line: #30363D;
          --polaris-green: #3DDC97;
          --polaris-red: #F85149;
          --polaris-amber: #E3B341;
          --polaris-blue: #4C9AFF;
        }
        .stApp {
          background:
            radial-gradient(circle at 14% -8%, rgba(61, 220, 151, .13), transparent 28rem),
            radial-gradient(circle at 96% 0%, rgba(76, 154, 255, .10), transparent 30rem),
            linear-gradient(180deg, #0E1117 0%, #0B0F14 100%);
          color: var(--polaris-ink);
        }
        .stApp::before {
          content: "";
          position: fixed;
          inset: 0;
          pointer-events: none;
          opacity: .05;
          background-image:
            linear-gradient(rgba(255,255,255,.22) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,.16) 1px, transparent 1px);
          background-size: 28px 28px;
          mask-image: linear-gradient(180deg, #000 0%, transparent 78%);
        }
        h1, h2, h3, p, label, span, div {
          letter-spacing: 0;
        }
        h1 {
          font-size: clamp(1.65rem, 2.4vw, 2.4rem);
          line-height: 1.12;
          font-weight: 750;
          text-wrap: balance;
        }
        h2, h3 {
          color: var(--polaris-ink);
        }
        [data-testid="stMetric"] {
          background: var(--polaris-surface);
          border: 1px solid var(--polaris-line);
          border-radius: 7px;
          padding: 14px 16px;
          box-shadow: 0 18px 42px rgba(0, 0, 0, .28);
        }
        [data-testid="stMetricLabel"], [data-testid="stCaptionContainer"] {
          color: var(--polaris-muted);
        }
        [data-testid="stMetricValue"] {
          color: var(--polaris-ink);
          font-variant-numeric: tabular-nums;
        }
        [data-testid="stDataFrame"] {
          border: 1px solid var(--polaris-line);
          border-radius: 7px;
          overflow: hidden;
          background: var(--polaris-surface);
        }
        div[data-testid="stAlert"] {
          border-radius: 8px;
        }
        .stTabs [data-baseweb="tab-list"] {
          gap: .35rem;
          border-bottom: 1px solid var(--polaris-line);
        }
        .stTabs [data-baseweb="tab"] {
          background: transparent;
          color: var(--polaris-muted);
          border-radius: 6px 6px 0 0;
        }
        .stTabs [aria-selected="true"] {
          color: var(--polaris-ink);
          background: var(--polaris-panel);
        }
        .polaris-hero {
          border: 1px solid var(--polaris-line);
          border-radius: 8px;
          background:
            linear-gradient(135deg, rgba(61, 220, 151, .13), transparent 44%),
            linear-gradient(180deg, #161B22, #0E1117);
          padding: 18px 20px;
          margin: 8px 0 14px;
          box-shadow: 0 20px 46px rgba(0, 0, 0, .26);
        }
        .polaris-eyebrow {
          color: var(--polaris-green);
          font-size: .78rem;
          font-weight: 700;
          margin-bottom: 6px;
        }
        .polaris-hero p {
          color: var(--polaris-muted);
          font-size: .98rem;
          line-height: 1.58;
          max-width: 88rem;
        }
        .polaris-grid {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 12px;
          margin: 14px 0 20px;
        }
        .polaris-card {
          background: var(--polaris-surface);
          border: 1px solid var(--polaris-line);
          border-radius: 7px;
          padding: 13px 14px;
        }
        .polaris-card .label {
          color: var(--polaris-muted);
          font-size: .82rem;
        }
        .polaris-card .value {
          color: var(--polaris-ink);
          font-size: 1.12rem;
          font-weight: 720;
          font-variant-numeric: tabular-nums;
          margin-top: 5px;
        }
        .polaris-note {
          border-left: 4px solid var(--polaris-amber);
          background: rgba(224, 180, 90, .08);
          padding: 12px 14px;
          border-radius: 6px;
          color: var(--polaris-ink);
          margin: 8px 0 12px;
        }
        .polaris-status {
          padding: 10px 12px;
          border: 1px solid var(--polaris-line);
          border-radius: 7px;
          background: var(--polaris-panel);
          color: var(--polaris-muted);
          margin-bottom: 12px;
        }
        .polaris-status strong {
          color: var(--polaris-ink);
        }
        .polaris-section {
          margin: 18px 0 10px;
          padding-top: 2px;
        }
        .polaris-section h2 {
          margin: 0;
          font-size: 1.12rem;
          line-height: 1.25;
        }
        .polaris-section p {
          color: var(--polaris-muted);
          margin: 5px 0 0;
          max-width: 72rem;
        }
        .polaris-intro {
          border: 1px solid var(--polaris-line);
          border-radius: 7px;
          background: rgba(33, 38, 45, .72);
          padding: 12px 14px;
          margin: 6px 0 14px;
        }
        .polaris-intro p {
          margin: 0;
          color: var(--polaris-muted);
          line-height: 1.55;
        }
        .polaris-intro strong {
          color: var(--polaris-ink);
        }
        .polaris-badge {
          display: inline-flex;
          align-items: center;
          border-radius: 999px;
          padding: 2px 8px;
          font-size: .78rem;
          font-weight: 700;
          line-height: 1.6;
          color: #0B0F14;
          font-variant-numeric: tabular-nums;
        }
        @media (max-width: 900px) {
          .polaris-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }
        }
        @media (max-width: 620px) {
          .polaris-grid {
            grid-template-columns: 1fr;
          }
          .polaris-hero {
            padding: 18px;
          }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def hero(title: str, body: str, eyebrow: str = "Polaris rotation workbench") -> None:
    st.markdown(
        f"""
        <section class="polaris-hero">
          <div class="polaris-eyebrow">{html.escape(eyebrow)}</div>
          <h1>{html.escape(title)}</h1>
          <p>{html.escape(plain_text(body))}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def metric_grid(items: list[tuple[str, str]]) -> None:
    columns = st.columns(len(items))
    for column, (label, value) in zip(columns, items):
        column.metric(label, value)


def page_intro(question: str, how_to: str) -> None:
    st.markdown(
        f"""
        <section class="polaris-intro">
          <p><strong>{html.escape(question)}</strong></p>
          <p>{html.escape(how_to)}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def plain_text(value: str) -> str:
    cleaned = (
        str(value or "")
        .replace("*", "")
        .replace("_", "")
        .replace("#", "")
        .replace("`", "")
        .replace("\r", " ")
        .replace("\n", " ")
    )
    return re.sub(r"\s+", " ", cleaned).strip()


def state_badge(state: str) -> str:
    label = str(state or "未知")
    matched_state = next(
        (name for name in STATE_COLORS if label.startswith(name)),
        label,
    )
    color = STATE_COLORS.get(matched_state, NEUTRAL_STATE_COLOR)
    return (
        f'<span class="polaris-badge" style="background:{html.escape(color)};">'
        f"{html.escape(label)}</span>"
    )


def card(title: str, body: str) -> None:
    with st.container(border=True):
        st.markdown(f"**{html.escape(title)}**")
        st.write(body)


def section(title: str, sub: str | None = None) -> None:
    subtitle = f"<p>{html.escape(sub)}</p>" if sub else ""
    st.markdown(
        f"""
        <section class="polaris-section">
          <h2>{html.escape(title)}</h2>
          {subtitle}
        </section>
        """,
        unsafe_allow_html=True,
    )


def plotly_template(fig):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=INK_COLOR, family="sans serif"),
        margin=dict(t=24, l=0, r=0, b=0),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=INK_COLOR)),
        xaxis=dict(
            gridcolor="rgba(139,148,158,.18)",
            zerolinecolor="rgba(139,148,158,.22)",
        ),
        yaxis=dict(
            gridcolor="rgba(139,148,158,.18)",
            zerolinecolor="rgba(139,148,158,.22)",
        ),
        coloraxis_colorbar=dict(outlinewidth=0, tickfont=dict(color=INK_COLOR)),
    )
    return fig


def note(text: str) -> None:
    st.markdown(
        f'<div class="polaris-note">{html.escape(text)}</div>',
        unsafe_allow_html=True,
    )


def status_line(text: str) -> None:
    st.markdown(
        f'<div class="polaris-status">{html.escape(text)}</div>',
        unsafe_allow_html=True,
    )


def format_percent(value) -> str:
    if pd.isna(value):
        return "-"
    return f"{float(value) * 100:.0f}%"


def format_signed_percent(value) -> str:
    if pd.isna(value):
        return "-"
    return f"{float(value):+.2f}%"


def format_money_yi(value) -> str:
    if pd.isna(value):
        return "-"
    return f"{float(value):,.0f} 亿"


def format_amount(value) -> str:
    if pd.isna(value):
        return "-"
    return f"{float(value) / 100000000:.2f} 亿"


def risk_label(value: str) -> str:
    labels = {"low": "低", "medium": "中", "high": "高"}
    return labels.get(value, value or "-")

"""Small Streamlit UI helpers for readable data-workbench pages."""

import pandas as pd
import streamlit as st


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
          --polaris-bg: #f5f7f4;
          --polaris-panel: #ffffff;
          --polaris-ink: #1d2522;
          --polaris-muted: #66736d;
          --polaris-line: #dfe6df;
          --polaris-accent: #216b4f;
        }
        .stApp {
          background: var(--polaris-bg);
          color: var(--polaris-ink);
        }
        h1, h2, h3 {
          letter-spacing: 0;
        }
        [data-testid="stMetric"] {
          background: var(--polaris-panel);
          border: 1px solid var(--polaris-line);
          border-radius: 8px;
          padding: 14px 16px;
        }
        [data-testid="stMetricLabel"] {
          color: var(--polaris-muted);
        }
        .polaris-note {
          border-left: 4px solid var(--polaris-accent);
          background: #ffffff;
          padding: 12px 14px;
          border-radius: 6px;
          color: var(--polaris-ink);
          margin: 8px 0 16px;
        }
        .polaris-kicker {
          color: var(--polaris-muted);
          font-size: 0.92rem;
          line-height: 1.55;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def note(text: str) -> None:
    st.markdown(f'<div class="polaris-note">{text}</div>', unsafe_allow_html=True)


def format_percent(value) -> str:
    if pd.isna(value):
        return "-"
    return f"{float(value) * 100:.1f}%"


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

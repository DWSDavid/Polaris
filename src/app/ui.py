"""Streamlit UI helpers for the Polaris decision workbench."""

from __future__ import annotations

import html

import pandas as pd
import streamlit as st


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
          --polaris-bg: #10130f;
          --polaris-surface: #171c15;
          --polaris-panel: #20271e;
          --polaris-panel-2: #273024;
          --polaris-ink: #f2efe4;
          --polaris-muted: #a9b2a2;
          --polaris-line: #3a4435;
          --polaris-green: #86c98a;
          --polaris-red: #d66a5d;
          --polaris-amber: #e0b45a;
          --polaris-blue: #8fb8d8;
        }
        .stApp {
          background:
            radial-gradient(circle at 12% 0%, rgba(134, 201, 138, .12), transparent 32rem),
            linear-gradient(180deg, #10130f 0%, #141812 100%);
          color: var(--polaris-ink);
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
          border-radius: 8px;
          padding: 14px 16px;
          box-shadow: 0 18px 42px rgba(0, 0, 0, .24);
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
          border-radius: 8px;
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
            linear-gradient(135deg, rgba(134, 201, 138, .10), transparent 42%),
            linear-gradient(180deg, #1a2118, #121611);
          padding: 16px 18px;
          margin: 8px 0 12px;
          box-shadow: 0 16px 34px rgba(0, 0, 0, .20);
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
          background: #151a13;
          border: 1px solid var(--polaris-line);
          border-radius: 8px;
          padding: 11px 12px;
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
          border-radius: 8px;
          background: var(--polaris-panel);
          color: var(--polaris-muted);
          margin-bottom: 12px;
        }
        .polaris-status strong {
          color: var(--polaris-ink);
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
          <p>{html.escape(body)}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def metric_grid(items: list[tuple[str, str]]) -> None:
    cards = "\n".join(f"""
        <div class="polaris-card">
          <div class="label">{html.escape(label)}</div>
          <div class="value">{html.escape(value)}</div>
        </div>
        """ for label, value in items)
    st.markdown(f'<div class="polaris-grid">{cards}</div>', unsafe_allow_html=True)


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

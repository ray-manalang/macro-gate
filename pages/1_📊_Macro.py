"""
pages/1_📊_Macro.py
Macro Deployment Gate — 6 signals, composite score, SPY backtest.
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from signals import vix_level, vix_term_structure, breadth, credit_spreads, put_call, crowding
from signals import composite as composite_mod
from backtest import deployment_backtest as bt

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Macro Deployment Gate",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Dark theme ─────────────────────────────────────────────────────────────────
BG      = "#0b0e17"
CARD_BG = "#131720"
BORDER  = "#1e2535"
TEXT    = "#e0e6f0"
MUTED   = "#6b7a99"

st.markdown(f"""
<style>
    .stApp {{ background-color: {BG}; color: {TEXT}; }}
    .block-container {{ padding-top: 1.5rem; padding-bottom: 2rem; }}
    .metric-card {{
        background: {CARD_BG};
        border: 1px solid {BORDER};
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 0.5rem;
    }}
    .signal-label {{ font-size: 0.75rem; color: {MUTED}; text-transform: uppercase; letter-spacing: 0.08em; }}
    .signal-score {{ font-size: 2rem; font-weight: 700; }}
    .signal-detail {{ font-size: 0.75rem; color: {MUTED}; margin-top: 0.2rem; }}
    .deploy-score {{ font-size: 6rem; font-weight: 900; line-height: 1; }}
    .deploy-label {{ font-size: 1.1rem; letter-spacing: 0.15em; font-weight: 600; margin-top: 0.3rem; }}
    .sizing-text {{ font-size: 0.9rem; color: {MUTED}; margin-top: 0.4rem; }}
    hr {{ border-color: {BORDER}; }}
    .stDataFrame {{ background: {CARD_BG}; }}
    div[data-testid="stMetricValue"] {{ color: {TEXT}; }}
</style>
""", unsafe_allow_html=True)

ZONE_COLORS = {
    "FULL DEPLOY": "#00ff88",
    "REDUCED":     "#ffaa00",
    "DEFENSIVE":   "#ff4444",
}
ZONE_SIZING = {
    "FULL DEPLOY": "100% sizing · new longs OK · scanner ON",
    "REDUCED":     "60% sizing · higher bar for new positions",
    "DEFENSIVE":   "25% sizing · no new longs · scanner OFF",
}


def score_color(score: float) -> str:
    if score >= 70:   return "#00ff88"
    elif score >= 40: return "#ffaa00"
    else:             return "#ff4444"


def make_gauge(score: float, label: str) -> go.Figure:
    color = score_color(score)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title={"text": label, "font": {"size": 11, "color": MUTED}},
        number={"font": {"size": 24, "color": color}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": MUTED, "tickfont": {"size": 9}},
            "bar": {"color": color, "thickness": 0.3},
            "bgcolor": CARD_BG,
            "borderwidth": 0,
            "steps": [
                {"range": [0, 40],   "color": "#1a0a0a"},
                {"range": [40, 70],  "color": "#1a1200"},
                {"range": [70, 100], "color": "#0a1a10"},
            ],
            "threshold": {"line": {"color": color, "width": 3}, "thickness": 0.8, "value": score},
        },
    ))
    fig.update_layout(height=160, margin=dict(l=10, r=10, t=40, b=10),
                      paper_bgcolor=CARD_BG, font_color=TEXT)
    return fig


@st.cache_data(ttl=900, show_spinner=False)
def load_signals():
    import yfinance as yf
    with st.spinner("Fetching VIX data..."):
        vix_data  = yf.Ticker("^VIX").history(period="400d")["Close"].dropna()
        vix3m_data = yf.Ticker("^VIX3M").history(period="400d")["Close"].dropna()
    results = [
        vix_level.score(vix_data),
        vix_term_structure.score(vix_data, vix3m_data),
    ]
    with st.spinner("Computing market breadth (~100 stocks)..."):
        results.append(breadth.score())
    with st.spinner("Fetching credit spreads..."):
        results.append(credit_spreads.score())
    results.append(put_call.score(vix_data))
    with st.spinner("Computing factor crowding..."):
        results.append(crowding.score())
    return results, composite_mod.compute(results)


@st.cache_data(ttl=3600, show_spinner=False)
def load_backtest():
    return bt.run_backtest(lookback_days=504)


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    f'<div style="display:flex;align-items:center;gap:1rem;margin-bottom:0.5rem;">'
    f'<span style="background:#1565c0;color:white;padding:0.2rem 0.6rem;'
    f'border-radius:4px;font-weight:700;font-size:0.8rem;">L1</span>'
    f'<span style="font-size:1.6rem;font-weight:800;letter-spacing:0.04em;">MACRO DEPLOYMENT GATE</span>'
    f'</div>'
    f'<div style="color:{MUTED};font-size:0.82rem;margin-bottom:1.5rem;">'
    f'6 macro signals · composite score 0–100 · deployment zone gating</div>',
    unsafe_allow_html=True,
)

col_r1, col_r2 = st.columns([8, 1])
with col_r2:
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

try:
    signal_results, comp = load_signals()
except Exception as e:
    st.error(f"Error loading signals: {e}")
    st.info("Check your internet connection and that yfinance can reach Yahoo Finance.")
    st.stop()

zone       = comp["zone"]
zone_color = ZONE_COLORS[zone]
composite  = comp["composite_score"]

# Store zone in session state for the Analyst page to read
st.session_state["macro_zone"]  = zone
st.session_state["macro_score"] = composite

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown("---")
hero_col, info_col = st.columns([1, 2])

with hero_col:
    st.markdown(
        f'<div style="text-align:center;padding:1.5rem 0;">'
        f'<div style="color:{MUTED};font-size:0.8rem;text-transform:uppercase;'
        f'letter-spacing:0.12em;margin-bottom:0.5rem;">Deployment Score</div>'
        f'<div class="deploy-score" style="color:{zone_color};">{composite:.0f}</div>'
        f'<div style="color:{MUTED};font-size:0.75rem;">out of 100</div>'
        f'<div class="deploy-label" style="color:{zone_color};margin-top:1rem;">{zone}</div>'
        f'<div class="sizing-text">{ZONE_SIZING[zone]}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

with info_col:
    st.markdown("#### Signal Contributions")
    breakdown  = comp["breakdown"]
    contrib_df = pd.DataFrame(breakdown)[["signal", "score", "weight", "contribution"]]
    contrib_df.columns = ["Signal", "Score", "Weight", "Contribution"]
    contrib_df["Score"]        = contrib_df["Score"].map("{:.1f}".format)
    contrib_df["Weight"]       = contrib_df["Weight"].map("{:.0%}".format)
    contrib_df["Contribution"] = contrib_df["Contribution"].map("{:.2f}".format)
    st.dataframe(contrib_df, use_container_width=True, hide_index=True)

# ── Gauges ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### Signal Gauges")
gauge_cols   = st.columns(6)
signal_order = ["VIX Level","VIX Term Structure","Market Breadth","Credit Spreads","Put/Call Sentiment","Factor Crowding"]
results_by_name = {r["signal"]: r for r in signal_results}

for col, sig_name in zip(gauge_cols, signal_order):
    res    = results_by_name.get(sig_name, {})
    s      = res.get("score", 0)
    detail = res.get("detail", "")
    with col:
        st.plotly_chart(make_gauge(s, sig_name.replace(" ", "<br>")),
                        use_container_width=True, config={"displayModeBar": False})
        st.markdown(f'<div class="signal-detail" style="text-align:center;">{detail}</div>',
                    unsafe_allow_html=True)

# ── Backtest ──────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### Historical Backtest — 2 Year")
st.caption("Yesterday's score used for today's allocation (no look-ahead). Breadth/crowding approximated via SPY-based proxies in backtest.")

with st.spinner("Running 2-year backtest..."):
    try:
        bt_df = load_backtest()
    except Exception as e:
        st.warning(f"Backtest failed: {e}")
        bt_df = None

if bt_df is not None:
    fig_spy = go.Figure()
    for zone_name, z_color in ZONE_COLORS.items():
        mask = bt_df["zone"] == zone_name
        if not mask.any():
            continue
        in_zone = False; start_date = None
        for date, flag in mask.items():
            if flag and not in_zone:
                start_date = date; in_zone = True
            elif not flag and in_zone:
                fig_spy.add_vrect(x0=start_date, x1=date,
                                  fillcolor=z_color, opacity=0.12, layer="below", line_width=0)
                in_zone = False
        if in_zone and start_date:
            fig_spy.add_vrect(x0=start_date, x1=bt_df.index[-1],
                              fillcolor=z_color, opacity=0.12, layer="below", line_width=0)

    fig_spy.add_trace(go.Scatter(x=bt_df.index, y=bt_df["spy_close"],
                                 line=dict(color="#4fc3f7", width=2), name="SPY",
                                 hovertemplate="%{x|%Y-%m-%d}<br>SPY: $%{y:.2f}<extra></extra>"))
    fig_spy.add_trace(go.Scatter(x=bt_df.index, y=bt_df["composite_score"],
                                 line=dict(color="#ffffff", width=1, dash="dot"),
                                 name="Gate Score", yaxis="y2", opacity=0.6,
                                 hovertemplate="%{x|%Y-%m-%d}<br>Score: %{y:.1f}<extra></extra>"))
    fig_spy.update_layout(
        paper_bgcolor=CARD_BG, plot_bgcolor=BG, font_color=TEXT,
        height=380, margin=dict(l=60, r=60, t=20, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)", font_size=11),
        xaxis=dict(gridcolor=BORDER, showgrid=True),
        yaxis=dict(title="SPY ($)", gridcolor=BORDER, showgrid=True),
        yaxis2=dict(title="Gate Score", overlaying="y", side="right",
                    range=[0, 100], showgrid=False, tickfont=dict(color=MUTED)),
        hovermode="x unified",
    )
    for zone_name, z_color in ZONE_COLORS.items():
        fig_spy.add_annotation(
            text=f"● {zone_name}", xref="paper", yref="paper",
            x=0.01 if zone_name == "FULL DEPLOY" else (0.18 if zone_name == "REDUCED" else 0.32),
            y=1.04, showarrow=False, font=dict(size=10, color=z_color),
        )
    st.plotly_chart(fig_spy, use_container_width=True, config={"displayModeBar": False})

    perf_df = bt.zone_performance(bt_df)
    st.markdown("##### Average SPY Performance by Deployment Zone")
    st.dataframe(perf_df, use_container_width=True, hide_index=True)

    zone_cum = {}
    for zone_name in ["FULL DEPLOY", "REDUCED", "DEFENSIVE"]:
        zone_rets = bt_df[bt_df["zone"] == zone_name]["spy_daily_return"].dropna()
        zone_cum[zone_name] = (1 + zone_rets).prod() - 1

    c1, c2, c3 = st.columns(3)
    for col, (zone_name, cum_ret) in zip([c1, c2, c3], zone_cum.items()):
        z_color = ZONE_COLORS[zone_name]
        col.markdown(
            f'<div class="metric-card" style="border-color:{z_color}33;">'
            f'<div class="signal-label">{zone_name}</div>'
            f'<div class="signal-score" style="color:{z_color};">{cum_ret:+.1%}</div>'
            f'<div class="signal-detail">cumulative SPY return (days in zone)</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    f'<div style="color:{MUTED};font-size:0.72rem;text-align:center;">'
    f'Data via yfinance (Yahoo Finance) · Scores refresh every 15 min · '
    f'Backtest uses SPY-based proxies for breadth/crowding · Not financial advice'
    f'</div>',
    unsafe_allow_html=True,
)

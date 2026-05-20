"""
pages/2_🧠_Analyst.py
----------------------
L3 Claude Analyst — standalone fundamental quality ranker.

No scanner required: user pastes a watchlist of tickers.
Claude scores each on 5 fundamental dimensions (1-10) and produces
a composite fundamental quality ranking.
"""

import os
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from analyst.analyzer import analyze_candidate, init_db, DB_PATH

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Claude Analyst | Macro Gate",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

BG      = "#0b0e17"
CARD_BG = "#131720"
BORDER  = "#1e2535"
TEXT    = "#e0e6f0"
MUTED   = "#6b7a99"

st.markdown(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap');
  html, body, [class*="css"] {{ font-family: 'DM Sans', sans-serif; background-color: {BG}; color: {TEXT}; }}
  .block-container {{ padding-top: 1.5rem; padding-bottom: 2rem; }}
  .main-title {{
    font-family: 'Space Mono', monospace; font-size: 2rem; font-weight: 700;
    letter-spacing: -0.03em; color: {TEXT}; line-height: 1.1;
  }}
  .sub-caption {{
    font-family: 'Space Mono', monospace; font-size: 0.7rem; color: {MUTED};
    letter-spacing: 0.12em; text-transform: uppercase; margin-top: 4px;
  }}
  .metric-card {{ background: {CARD_BG}; border: 1px solid {BORDER}; border-radius: 8px; padding: 16px 20px; }}
  .metric-label {{
    font-family: 'Space Mono', monospace; font-size: 0.62rem; color: {MUTED};
    letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 6px;
  }}
  .metric-value {{ font-family: 'Space Mono', monospace; font-size: 1.6rem; font-weight: 700; color: {TEXT}; line-height: 1; }}
  .metric-sub {{ font-size: 0.72rem; color: {MUTED}; margin-top: 4px; }}
  hr {{ border-color: {BORDER}; }}
  .stDataFrame {{ border: 1px solid {BORDER} !important; }}
</style>
""", unsafe_allow_html=True)

DEFAULT_TICKERS = (
    "AAPL MSFT GOOGL META NVDA AMZN TSLA JPM UNH V MA HD PG JNJ XOM"
)

SCORE_DIMS = [
    ("Earnings Quality",    "earnings_quality"),
    ("Growth Trajectory",   "growth_trajectory"),
    ("Balance Sheet",       "balance_sheet_health"),
    ("Margin Trends",       "margin_trends"),
    ("Red Flags (inv.)",    "red_flags"),
]


def metric_card(label, value, sub=""):
    sub_html = f'<div class="metric-sub">{sub}</div>' if sub else ""
    return f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div>{sub_html}</div>'


def load_cached_notes(tickers: list[str]) -> dict[str, dict]:
    if not os.path.exists(DB_PATH):
        return {}
    conn = sqlite3.connect(DB_PATH)
    placeholders = ",".join("?" * len(tickers))
    rows = conn.execute(
        f"""SELECT ticker, earnings_quality, growth_trajectory, balance_sheet_health,
                   margin_trends, red_flags, composite_fundamental_score, analyst_notes
            FROM fundamental_scores
            WHERE ticker IN ({placeholders})
            ORDER BY scored_at DESC""",
        tickers,
    ).fetchall()
    conn.close()
    seen: set = set()
    result = {}
    for row in rows:
        t = row[0]
        if t not in seen:
            seen.add(t)
            result[t] = {
                "earnings_quality":            row[1],
                "growth_trajectory":           row[2],
                "balance_sheet_health":        row[3],
                "margin_trends":               row[4],
                "red_flags":                   row[5],
                "composite_fundamental_score": row[6],
                "analyst_notes":               row[7],
            }
    return result


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Analyst Controls")

    api_key_input = st.text_input(
        "Anthropic API Key",
        value=os.getenv("ANTHROPIC_API_KEY", ""),
        type="password",
        help="Required. Set ANTHROPIC_API_KEY env var to avoid entering it here.",
    )
    if api_key_input:
        os.environ["ANTHROPIC_API_KEY"] = api_key_input

    st.divider()

    raw_input = st.text_area(
        "Tickers to analyze",
        value=DEFAULT_TICKERS,
        height=160,
        help="Space or newline separated. E.g.  AAPL MSFT GOOGL",
    )

    st.divider()
    run_btn   = st.button("🧠  Run Fundamental Analysis", use_container_width=True, type="primary")
    clear_btn = st.button("🗑  Clear Cache", use_container_width=True)

    if clear_btn:
        if os.path.exists(DB_PATH):
            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM fundamental_scores")
            conn.commit()
            conn.close()
        st.session_state.pop("analyst_results_mg", None)
        st.success("Cache cleared.")

    st.divider()
    st.markdown("""
**Scoring dimensions (1–10)**
1. Earnings quality (CFO/NI, accruals)
2. Growth trajectory (revenue, FCF trend)
3. Balance sheet health (D/E, liquidity)
4. Margin trends (gross & operating)
5. Red flags — inverted (lower = safer)
""")

# ── Header ────────────────────────────────────────────────────────────────────
# Show macro zone badge if coming from Page 1
zone  = st.session_state.get("macro_zone")
score = st.session_state.get("macro_score")
zone_colors = {"FULL DEPLOY": "#00ff88", "REDUCED": "#ffaa00", "DEFENSIVE": "#ff4444"}

zone_badge = ""
if zone:
    z_color    = zone_colors.get(zone, MUTED)
    zone_badge = (
        f'&nbsp;&nbsp;<span style="background:{z_color}22;color:{z_color};border:1px solid {z_color}44;'
        f'padding:2px 12px;border-radius:3px;font-size:0.75rem;font-weight:700;'
        f'font-family:Space Mono,monospace;">{zone} · {score:.0f}</span>'
        if score is not None else ""
    )

st.markdown(
    f'<div style="display:flex;align-items:center;gap:1rem;margin-bottom:0.5rem;">'
    f'<span style="background:#7c3aed;color:white;padding:0.2rem 0.6rem;'
    f'border-radius:4px;font-weight:700;font-size:0.8rem;">L3</span>'
    f'<div class="main-title">CLAUDE ANALYST LAYER</div>{zone_badge}'
    f'</div>'
    f'<div class="sub-caption">fundamental quality scoring · earnings · growth · balance sheet · margins</div>',
    unsafe_allow_html=True,
)
st.markdown("---")

# ── Parse tickers ─────────────────────────────────────────────────────────────
tickers = [t.strip().upper() for t in raw_input.replace(",", " ").split() if t.strip()]
tickers = list(dict.fromkeys(tickers))  # deduplicate, preserve order

if not tickers:
    st.warning("Enter at least one ticker in the sidebar.")
    st.stop()

# ── Run analysis ──────────────────────────────────────────────────────────────
if run_btn:
    if not os.getenv("ANTHROPIC_API_KEY"):
        st.error("Enter your Anthropic API key in the sidebar before running.")
        st.stop()

    progress_bar      = st.progress(0, text="Starting…")
    status_placeholder = st.empty()
    results_list       = []

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    for i, ticker in enumerate(tickers):
        status_placeholder.markdown(
            f'<div style="font-family:Space Mono,monospace;font-size:0.8rem;color:{MUTED};">'
            f'Analyzing {ticker} ({i+1}/{len(tickers)})…</div>',
            unsafe_allow_html=True,
        )
        progress_bar.progress((i + 1) / len(tickers), text=f"Analyzing {ticker}…")
        results_list.append(analyze_candidate(ticker, conn))

    conn.close()
    progress_bar.empty()
    status_placeholder.empty()

    st.session_state["analyst_results_mg"] = results_list
    st.success(f"Analysis complete — {len(tickers)} tickers scored.")

# ── Load results (from session state or cache DB) ─────────────────────────────
results_list = st.session_state.get("analyst_results_mg")

if results_list is None:
    notes_map = load_cached_notes(tickers)
    if notes_map:
        results_list = [
            {"ticker": t, **notes_map[t]} if t in notes_map
            else {"ticker": t, "composite_fundamental_score": None}
            for t in tickers
        ]
        st.session_state["analyst_results_mg"] = results_list

if not results_list:
    st.info(
        f"No analysis run yet. Enter tickers in the sidebar and click **🧠 Run Fundamental Analysis** "
        f"to score {len(tickers)} tickers.",
        icon="ℹ️",
    )
    st.stop()

# ── Build ranked DataFrame ────────────────────────────────────────────────────
rows = []
for r in results_list:
    t = r.get("ticker", "?")
    rows.append({
        "ticker":     t,
        "fund_score": r.get("composite_fundamental_score"),
        "earnings_quality":      r.get("earnings_quality"),
        "growth_trajectory":     r.get("growth_trajectory"),
        "balance_sheet_health":  r.get("balance_sheet_health"),
        "margin_trends":         r.get("margin_trends"),
        "red_flags":             r.get("red_flags"),
        "error":                 r.get("error"),
    })

df = pd.DataFrame(rows)
df_scored  = df[df["fund_score"].notna()].sort_values("fund_score", ascending=False).reset_index(drop=True)
df_scored["rank"] = range(1, len(df_scored) + 1)
df_failed  = df[df["fund_score"].isna()]

# ── KPI strip ─────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(metric_card("Analyzed", str(len(df_scored)), f"of {len(tickers)} tickers"), unsafe_allow_html=True)
with c2:
    avg = df_scored["fund_score"].mean() if not df_scored.empty else 0
    st.markdown(metric_card("Avg Score", f"{avg:.1f}/10", "composite fundamental"), unsafe_allow_html=True)
with c3:
    top = df_scored.iloc[0] if not df_scored.empty else None
    st.markdown(metric_card("Top Ranked", top["ticker"] if top is not None else "—",
                             f"score {top['fund_score']:.1f}/10" if top is not None else ""), unsafe_allow_html=True)
with c4:
    bottom = df_scored.iloc[-1] if not df_scored.empty else None
    st.markdown(metric_card("Lowest Ranked", bottom["ticker"] if bottom is not None else "—",
                             f"score {bottom['fund_score']:.1f}/10" if bottom is not None else ""), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Chart + Table ─────────────────────────────────────────────────────────────
col_chart, col_table = st.columns([2, 3])

with col_chart:
    st.markdown("#### Fundamental Quality Ranking")

    def bar_color(v):
        if v >= 8:  return "#4ade80"
        if v >= 6:  return "#a3e635"
        if v >= 4:  return "#facc15"
        if v >= 2:  return "#fb923c"
        return "#f87171"

    colors = [bar_color(v) for v in df_scored["fund_score"]]
    fig = go.Figure(go.Bar(
        x=df_scored["fund_score"],
        y=df_scored["ticker"],
        orientation="h",
        marker_color=colors,
        marker_line_width=0,
        text=df_scored["fund_score"].round(1),
        textposition="outside",
        textfont=dict(size=10, color="#94a3b8", family="Space Mono"),
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(autorange="reversed", tickfont=dict(family="Space Mono", size=11, color="#cbd5e1")),
        xaxis=dict(range=[0, 11], gridcolor=BORDER, tickfont=dict(size=10, color="#64748b")),
        margin=dict(l=10, r=40, t=10, b=10),
        height=max(300, len(df_scored) * 28),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

with col_table:
    st.markdown("#### Full Scores Table")

    display_cols = ["rank", "ticker", "fund_score",
                    "earnings_quality", "growth_trajectory",
                    "balance_sheet_health", "margin_trends", "red_flags"]
    col_labels = ["Rank", "Ticker", "Composite", "Earnings", "Growth", "Balance Sheet", "Margins", "Red Flags"]

    show = df_scored[display_cols].copy()
    show.columns = col_labels

    def color_score(val):
        try:
            v = float(val)
            if v >= 8: return "color: #4ade80"
            if v >= 6: return "color: #a3e635"
            if v >= 4: return "color: #facc15"
            return "color: #f87171"
        except Exception:
            return ""

    score_cols = col_labels[2:]
    styled = (
        show.style
        .applymap(color_score, subset=score_cols)
        .format({c: "{:.1f}" for c in score_cols}, na_rep="—")
        .set_properties(**{"font-size": "12px", "font-family": "Space Mono, monospace"})
    )
    st.dataframe(styled, use_container_width=True, height=min(400, 60 + len(df_scored) * 35))

# Failed tickers
if not df_failed.empty:
    with st.expander(f"⚠ {len(df_failed)} tickers failed (click to expand)"):
        for _, row in df_failed.iterrows():
            st.markdown(f"**{row['ticker']}** — {row.get('error', 'unknown error')}")

# ── Expandable Analyst Notes ──────────────────────────────────────────────────
st.markdown("---")
st.subheader("🔍 Analyst Notes")
st.caption("Claude's narrative summary and sub-scores for each ticker.")

notes_map = load_cached_notes(df_scored["ticker"].tolist())

for _, row in df_scored.iterrows():
    ticker = row["ticker"]
    data   = notes_map.get(ticker, {})

    score_val = row["fund_score"]
    if score_val >= 7:   badge = "🟢"
    elif score_val >= 4: badge = "🟡"
    else:                badge = "🔴"

    with st.expander(f"{badge} #{int(row['rank'])}  {ticker}  —  {score_val:.1f}/10"):
        sub_cols = st.columns(5)
        for col, (label, key) in zip(sub_cols, SCORE_DIMS):
            val = data.get(key)
            col.metric(label, f"{val:.1f}/10" if val is not None else "—")

        notes = data.get("analyst_notes", "")
        if notes:
            st.markdown(
                f'<div style="background:{CARD_BG};border-left:3px solid #7c3aed;'
                f'padding:12px 16px;border-radius:4px;font-size:0.88rem;color:{TEXT};margin-top:8px;">'
                f'{notes}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.info("No narrative notes cached.")

# ── Download ──────────────────────────────────────────────────────────────────
st.markdown("---")
csv = df_scored.to_csv(index=False).encode("utf-8")
st.download_button(
    label="⬇  Download Results CSV",
    data=csv,
    file_name=f"fundamental_scores_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
    mime="text/csv",
)

st.markdown(
    f'<div style="color:{MUTED};font-size:0.72rem;text-align:center;margin-top:1rem;">'
    f'Fundamentals via yfinance · Scored by Claude · DB: <code>{DB_PATH}</code> · Not financial advice'
    f'</div>',
    unsafe_allow_html=True,
)

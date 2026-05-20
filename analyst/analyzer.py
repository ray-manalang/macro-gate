"""
analyst/analyzer.py
-------------------
L3 Claude Analyst: fetches fundamentals via yfinance, scores each candidate
on fundamental quality using Claude API, and caches results in a shared
SQLite DB keyed by (ticker, quarter_end).
"""

import json
import sqlite3
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import anthropic
import yfinance as yf
import pandas as pd

# ── Config ────────────────────────────────────────────────────────────────────
_DEFAULT_DB = str(Path(__file__).parent.parent / "analyst_cache.db")
DB_PATH = os.getenv("DB_PATH", _DEFAULT_DB)
CLAUDE_MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are a senior equity research analyst with deep expertise in
fundamental analysis. You will be given 4 quarters of financial data for a stock.

Score the company 1-10 on each of the following dimensions:
- earnings_quality: Accruals, CFO/NI ratio, revenue recognition red flags
- growth_trajectory: Revenue, income, FCF trend and acceleration/deceleration
- balance_sheet_health: Debt/equity, leverage trend, liquidity
- margin_trends: Gross and operating margin direction and stability
- red_flags: Earnings manipulation signals, AR > revenue growth, unusual items

Respond ONLY with a valid JSON object in exactly this format, no preamble:
{
  "earnings_quality": <1-10>,
  "growth_trajectory": <1-10>,
  "balance_sheet_health": <1-10>,
  "margin_trends": <1-10>,
  "red_flags": <1-10>,
  "composite_fundamental_score": <1-10>,
  "analyst_notes": "<2-3 sentence summary of key findings>"
}"""


# ── DB Setup ──────────────────────────────────────────────────────────────────
def init_db(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fundamental_scores (
            ticker          TEXT NOT NULL,
            quarter_end     TEXT NOT NULL,
            earnings_quality        REAL,
            growth_trajectory       REAL,
            balance_sheet_health    REAL,
            margin_trends           REAL,
            red_flags               REAL,
            composite_fundamental_score REAL,
            analyst_notes   TEXT,
            raw_financials  TEXT,
            scored_at       TEXT,
            PRIMARY KEY (ticker, quarter_end)
        )
    """)
    conn.commit()


def get_cached_score(conn: sqlite3.Connection, ticker: str, quarter_end: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM fundamental_scores WHERE ticker=? AND quarter_end=?",
        (ticker, quarter_end)
    ).fetchone()
    if row:
        cols = [d[0] for d in conn.execute(
            "SELECT * FROM fundamental_scores LIMIT 0"
        ).description]
        return dict(zip(cols, row))
    return None


def save_score(conn: sqlite3.Connection, ticker: str, quarter_end: str,
               scores: dict, raw_financials: dict):
    conn.execute("""
        INSERT OR REPLACE INTO fundamental_scores
        (ticker, quarter_end, earnings_quality, growth_trajectory,
         balance_sheet_health, margin_trends, red_flags,
         composite_fundamental_score, analyst_notes, raw_financials, scored_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (
        ticker, quarter_end,
        scores.get("earnings_quality"),
        scores.get("growth_trajectory"),
        scores.get("balance_sheet_health"),
        scores.get("margin_trends"),
        scores.get("red_flags"),
        scores.get("composite_fundamental_score"),
        scores.get("analyst_notes"),
        json.dumps(raw_financials),
        datetime.utcnow().isoformat()
    ))
    conn.commit()


# ── Fundamentals Fetch ────────────────────────────────────────────────────────
def fetch_fundamentals(ticker: str) -> tuple[dict, str]:
    """
    Returns (financials_dict, quarter_end_string).
    Pulls last 4 quarters from yfinance and computes derived ratios.
    """
    tk = yf.Ticker(ticker)

    income_q = tk.quarterly_income_stmt
    cashflow_q = tk.quarterly_cashflow
    balance_q = tk.quarterly_balance_sheet

    def safe_row(df: pd.DataFrame, *row_names) -> pd.Series:
        for name in row_names:
            if name in df.index:
                return df.loc[name].iloc[:4]
        return pd.Series([None] * 4)

    revenue      = safe_row(income_q, "Total Revenue", "Revenue")
    net_income   = safe_row(income_q, "Net Income", "Net Income Common Stockholders")
    gross_profit = safe_row(income_q, "Gross Profit")
    op_income    = safe_row(income_q, "Operating Income", "EBIT")
    op_cashflow  = safe_row(cashflow_q, "Operating Cash Flow", "Total Cash From Operating Activities")
    capex        = safe_row(cashflow_q, "Capital Expenditure", "Purchase Of PPE")
    total_debt   = safe_row(balance_q, "Total Debt", "Long Term Debt")
    equity       = safe_row(balance_q, "Stockholders Equity", "Total Stockholder Equity")
    accounts_rec = safe_row(balance_q, "Accounts Receivable", "Net Receivables")

    def pct_list(series: pd.Series) -> list:
        vals = series.tolist()
        return [round(float(v), 2) if v is not None and pd.notna(v) else None for v in vals]

    def ratio(a, b):
        try:
            return round(float(a) / float(b), 4) if b and float(b) != 0 else None
        except Exception:
            return None

    fcf = []
    for ocf, cx in zip(op_cashflow.tolist(), capex.tolist()):
        try:
            fcf.append(round(float(ocf) + float(cx), 2))
        except Exception:
            fcf.append(None)

    gross_margin = [ratio(g, r) for g, r in zip(gross_profit.tolist(), revenue.tolist())]
    op_margin    = [ratio(o, r) for o, r in zip(op_income.tolist(), revenue.tolist())]
    debt_equity  = [ratio(d, e) for d, e in zip(total_debt.tolist(), equity.tolist())]
    roe          = [ratio(n, e) for n, e in zip(net_income.tolist(), equity.tolist())]
    cfo_ni       = [ratio(c, n) for c, n in zip(op_cashflow.tolist(), net_income.tolist())]

    def qoq_growth(series_list):
        try:
            curr, prev = float(series_list[0]), float(series_list[1])
            return round((curr - prev) / abs(prev), 4) if prev != 0 else None
        except Exception:
            return None

    ar_growth  = qoq_growth(accounts_rec.tolist())
    rev_growth = qoq_growth(revenue.tolist())

    try:
        quarter_end = str(income_q.columns[0].date())
    except Exception:
        quarter_end = datetime.utcnow().strftime("%Y-%m-%d")

    financials = {
        "ticker": ticker,
        "quarters": [str(c.date()) if hasattr(c, 'date') else str(c)
                     for c in income_q.columns[:4].tolist()],
        "revenue":        pct_list(revenue),
        "net_income":     pct_list(net_income),
        "op_cashflow":    pct_list(op_cashflow),
        "fcf":            fcf,
        "gross_margin":   gross_margin,
        "op_margin":      op_margin,
        "debt_equity":    debt_equity,
        "roe":            roe,
        "cfo_ni_ratio":   cfo_ni,
        "ar_growth_vs_rev_growth": {
            "ar_growth":  ar_growth,
            "rev_growth": rev_growth,
            "spread":     round(ar_growth - rev_growth, 4)
                          if ar_growth is not None and rev_growth is not None else None
        }
    }

    return financials, quarter_end


# ── Claude Scoring ────────────────────────────────────────────────────────────
def score_with_claude(financials: dict) -> dict:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set.")
    client = anthropic.Anthropic(api_key=api_key)

    user_msg = (
        f"Please score this company's fundamental quality.\n\n"
        f"Financial data (last 4 quarters, most recent first):\n"
        f"{json.dumps(financials, indent=2)}"
    )

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}]
    )

    raw_text = response.content[0].text.strip()
    raw_text = raw_text.replace("```json", "").replace("```", "").strip()
    return json.loads(raw_text)


# ── Public API ────────────────────────────────────────────────────────────────
def analyze_candidate(ticker: str, conn: sqlite3.Connection) -> dict:
    """Main entry point. Returns scores dict for a single ticker."""
    init_db(conn)

    try:
        financials, quarter_end = fetch_fundamentals(ticker)
    except Exception as e:
        return {"ticker": ticker, "error": str(e), "composite_fundamental_score": None}

    cached = get_cached_score(conn, ticker, quarter_end)
    if cached:
        return cached

    try:
        scores = score_with_claude(financials)
    except Exception as e:
        return {"ticker": ticker, "error": str(e), "composite_fundamental_score": None}

    save_score(conn, ticker, quarter_end, scores, financials)
    scores["ticker"] = ticker
    scores["quarter_end"] = quarter_end
    return scores


def analyze_candidates(tickers: list[str], db_path: str = DB_PATH) -> list[dict]:
    """Batch analyze a list of tickers. Returns list of score dicts."""
    conn = sqlite3.connect(db_path)
    results = []
    for ticker in tickers:
        result = analyze_candidate(ticker, conn)
        results.append(result)
    conn.close()
    return results

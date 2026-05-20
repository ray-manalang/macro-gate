"""
Signal 3: Market Breadth
% of S&P 500 stocks above their 200-day SMA.
80% -> 100, 30% -> 0.
Uses a representative 100-stock sample from S&P 500 sectors
(full universe requires paid data).
"""

import yfinance as yf
import numpy as np
import pandas as pd

# Representative S&P 500 sample across sectors (~100 stocks)
SP500_SAMPLE = [
    # Tech
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "AVGO", "ORCL", "CRM", "AMD",
    "INTC", "QCOM", "TXN", "NOW", "ADBE", "INTU", "MU", "AMAT", "LRCX", "KLAC",
    # Financials
    "JPM", "BAC", "WFC", "GS", "MS", "BLK", "C", "AXP", "USB", "PNC",
    "SCHW", "COF", "TFC", "CB", "MMC", "AON", "ICE", "CME", "SPGI", "MCO",
    # Healthcare
    "LLY", "JNJ", "ABBV", "MRK", "UNH", "TMO", "ABT", "DHR", "PFE", "BMY",
    "AMGN", "GILD", "ISRG", "VRTX", "REGN", "ZBH", "BSX", "MDT", "EW", "SYK",
    # Consumer
    "AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "TGT", "LOW", "BKNG", "MAR",
    "PG", "KO", "PEP", "COST", "WMT", "PM", "MO", "CL", "KMB", "GIS",
    # Energy & Industrials
    "XOM", "CVX", "COP", "SLB", "EOG", "PXD", "MPC", "VLO", "PSX", "OXY",
    "CAT", "DE", "HON", "GE", "MMM", "RTX", "LMT", "NOC", "BA", "UPS",
]
# Deduplicate
SP500_SAMPLE = list(dict.fromkeys(SP500_SAMPLE))


def pct_above_sma(tickers: list, period: str = "300d", sma_window: int = 200) -> float:
    """Return fraction of tickers currently above their 200-day SMA."""
    above = 0
    total = 0
    data = yf.download(
        tickers,
        period=period,
        auto_adjust=True,
        progress=False,
        threads=True,
    )["Close"]

    for ticker in tickers:
        if ticker not in data.columns:
            continue
        series = data[ticker].dropna()
        if len(series) < sma_window:
            continue
        sma = series.rolling(sma_window).mean().iloc[-1]
        current = series.iloc[-1]
        total += 1
        if current > sma:
            above += 1

    return above / total if total > 0 else 0.5


def breadth_to_score(pct: float) -> float:
    """Linear: 80% -> 100, 30% -> 0"""
    score = (pct - 0.30) / (0.80 - 0.30) * 100
    return float(np.clip(score, 0, 100))


def score(tickers: list = None) -> dict:
    if tickers is None:
        tickers = SP500_SAMPLE

    pct = pct_above_sma(tickers)
    final_score = breadth_to_score(pct)

    return {
        "signal": "Market Breadth",
        "score": final_score,
        "pct_above_200sma": pct,
        "stocks_sampled": len(tickers),
        "detail": f"{pct:.1%} of sample above 200-day SMA",
    }


if __name__ == "__main__":
    result = score()
    print(result)

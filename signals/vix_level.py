"""
Signal 1: VIX Level
Percentile-rank current VIX against trailing 1 year.
Low VIX = high score. Bonus +5 if VIX < 15. Penalty -10 if VIX > 30.
"""

import yfinance as yf
import numpy as np
import pandas as pd


def fetch_vix(period="400d") -> pd.Series:
    ticker = yf.Ticker("^VIX")
    hist = ticker.history(period=period)
    return hist["Close"].dropna()


def score(vix_series: pd.Series = None) -> dict:
    if vix_series is None:
        vix_series = fetch_vix()

    current_vix = float(vix_series.iloc[-1])
    trailing_1y = vix_series.iloc[-252:] if len(vix_series) >= 252 else vix_series

    # Percentile rank: low VIX = high percentile score
    pct_rank = float(np.sum(trailing_1y >= current_vix) / len(trailing_1y))
    raw_score = pct_rank * 100

    # Bonus / penalty
    if current_vix < 15:
        raw_score += 5
    if current_vix > 30:
        raw_score -= 10

    final_score = float(np.clip(raw_score, 0, 100))

    return {
        "signal": "VIX Level",
        "score": final_score,
        "current_vix": current_vix,
        "pct_rank": pct_rank,
        "detail": f"VIX={current_vix:.1f} | 1Y pct-rank={pct_rank:.1%}",
    }


if __name__ == "__main__":
    result = score()
    print(result)

"""
Signal 5: Put/Call Sentiment
VIX 20-day rate of change as proxy for put/call sentiment.
Rapidly rising VIX = fear = low score.
ROC -30% -> 100 (fear receding), ROC +50% -> 0 (fear surging).
"""

import yfinance as yf
import numpy as np
import pandas as pd


def fetch_vix(period="400d") -> pd.Series:
    ticker = yf.Ticker("^VIX")
    hist = ticker.history(period=period)
    return hist["Close"].dropna()


def roc_to_score(roc: float) -> float:
    """
    Linear interpolation: ROC -30% -> 100, ROC +50% -> 0.
    roc is expressed as a decimal (e.g., 0.30 = 30%).
    """
    roc_pct = roc * 100  # convert to percentage points
    score = (-roc_pct + 50) / (50 + 30) * 100
    return float(np.clip(score, 0, 100))


def score(vix_series: pd.Series = None) -> dict:
    if vix_series is None:
        vix_series = fetch_vix()

    if len(vix_series) < 21:
        return {
            "signal": "Put/Call Sentiment",
            "score": 50.0,
            "roc_20d": 0.0,
            "detail": "Insufficient data",
        }

    current = float(vix_series.iloc[-1])
    prior = float(vix_series.iloc[-21])
    roc = (current - prior) / prior if prior != 0 else 0.0

    final_score = roc_to_score(roc)
    sentiment = "fear" if roc > 0.1 else ("calm" if roc < -0.1 else "neutral")

    return {
        "signal": "Put/Call Sentiment",
        "score": final_score,
        "roc_20d": roc,
        "current_vix": current,
        "sentiment": sentiment,
        "detail": f"VIX 20d ROC={roc:+.1%} ({sentiment})",
    }


if __name__ == "__main__":
    result = score()
    print(result)

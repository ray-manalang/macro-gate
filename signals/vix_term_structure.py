import yfinance as yf
import numpy as np
import pandas as pd


def fetch_term_structure(period="400d"):
    vix = yf.Ticker("^VIX").history(period=period)["Close"].dropna()
    vix3m = yf.Ticker("^VIX3M").history(period=period)["Close"].dropna()
    return vix, vix3m


def ratio_to_score(ratio):
    score = (1.15 - ratio) / (1.15 - 0.85) * 100
    return float(np.clip(score, 0, 100))


def score(vix_series=None, vix3m_series=None):
    if vix_series is None or vix3m_series is None:
        vix_series, vix3m_series = fetch_term_structure()

    common = vix_series.index.intersection(vix3m_series.index)
    if len(common) == 0:
        return {"signal": "VIX Term Structure", "score": 50.0,
                "ratio": 1.0, "detail": "No overlapping data"}

    vix_aligned = vix_series.loc[common].dropna()
    vix3m_aligned = vix3m_series.loc[common].dropna()

    if len(vix_aligned) == 0 or len(vix3m_aligned) == 0:
        return {"signal": "VIX Term Structure", "score": 50.0,
                "ratio": 1.0, "detail": "Empty after alignment"}

    current_vix = float(vix_aligned.iloc[-1])
    current_vix3m = float(vix3m_aligned.iloc[-1])
    ratio = current_vix / current_vix3m if current_vix3m != 0 else 1.0
    final_score = ratio_to_score(ratio)
    structure = "contango" if ratio < 1.0 else "backwardation"

    return {
        "signal": "VIX Term Structure",
        "score": final_score,
        "vix": current_vix,
        "vix3m": current_vix3m,
        "ratio": ratio,
        "structure": structure,
        "detail": f"VIX/VIX3M={ratio:.3f} ({structure})",
    }

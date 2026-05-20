"""
Signal 4: Credit Spreads
HYG vs TLT spread proxy, z-score against 1-year history.
Tight spreads (z = -2) -> 100. Wide spreads (z = +2) -> 0.
"""

import yfinance as yf
import numpy as np
import pandas as pd


def fetch_credit_data(period="400d") -> pd.DataFrame:
    data = yf.download(
        ["HYG", "TLT"],
        period=period,
        auto_adjust=True,
        progress=False,
    )["Close"]
    return data.dropna()


def compute_spread_proxy(data: pd.DataFrame) -> pd.Series:
    """
    Spread proxy: TLT return - HYG return (relative performance).
    When credit is stressed, HYG underperforms TLT -> spread widens -> proxy rises.
    """
    hyg_ret = data["HYG"].pct_change()
    tlt_ret = data["TLT"].pct_change()
    spread = (tlt_ret - hyg_ret).rolling(20).mean() * 100  # smoothed
    return spread.dropna()


def zscore_to_score(z: float) -> float:
    """z = -2 -> 100 (tight spreads), z = +2 -> 0 (wide spreads)"""
    score = (-z + 2) / 4 * 100
    return float(np.clip(score, 0, 100))


def score(data: pd.DataFrame = None) -> dict:
    if data is None:
        data = fetch_credit_data()

    spread = compute_spread_proxy(data)
    trailing_1y = spread.iloc[-252:] if len(spread) >= 252 else spread

    current = float(spread.iloc[-1])
    mean = float(trailing_1y.mean())
    std = float(trailing_1y.std())
    z = (current - mean) / std if std > 0 else 0.0

    final_score = zscore_to_score(z)
    condition = "tight" if z < 0 else "wide"

    return {
        "signal": "Credit Spreads",
        "score": final_score,
        "spread_proxy": current,
        "z_score": z,
        "condition": condition,
        "detail": f"HYG/TLT spread z-score={z:.2f} ({condition})",
    }


if __name__ == "__main__":
    result = score()
    print(result)

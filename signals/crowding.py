"""
Signal 6: Factor Crowding
Build momentum and value long/short baskets from top/bottom 50 stocks.
60-day rolling correlation between factor returns.
Corr +0.3 -> 100 (normal). Corr -0.8 -> 0 (extreme crowding).
Highly negative correlation = momentum crowded = reversal risk.
"""

import yfinance as yf
import numpy as np
import pandas as pd

# Universe for factor construction
UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "AVGO", "ORCL", "CRM", "AMD",
    "JPM", "BAC", "WFC", "GS", "MS", "BLK", "C", "AXP", "USB", "PNC",
    "LLY", "JNJ", "ABBV", "MRK", "UNH", "TMO", "ABT", "DHR", "PFE", "BMY",
    "HD", "MCD", "NKE", "SBUX", "TGT", "LOW", "BKNG", "MAR", "PG", "KO",
    "XOM", "CVX", "COP", "SLB", "EOG", "CAT", "DE", "HON", "GE", "RTX",
    "PEP", "COST", "WMT", "PM", "MO", "CL", "KMB", "GIS", "MMM", "UPS",
    "SCHW", "COF", "TFC", "CB", "MMC", "AON", "ICE", "CME", "SPGI", "MCO",
    "AMGN", "GILD", "ISRG", "VRTX", "REGN", "BSX", "MDT", "EW", "SYK", "ZBH",
    "INTC", "QCOM", "TXN", "NOW", "ADBE", "INTU", "MU", "AMAT", "LRCX", "KLAC",
    "TSLA", "V", "MA", "PYPL", "SQ", "NFLX", "DIS", "CMCSA", "T", "VZ",
]
UNIVERSE = list(dict.fromkeys(UNIVERSE))


def build_factor_returns(period: str = "500d") -> pd.DataFrame:
    """Download prices and compute momentum/value long-short daily returns."""
    raw = yf.download(UNIVERSE, period=period, auto_adjust=True, progress=False)["Close"]
    raw = raw.dropna(axis=1, thresh=int(len(raw) * 0.8))  # drop sparse tickers

    # --- Momentum factor ---
    # Signal: 12-1 month return (252-day rolling, skip last 21 days)
    mom_signal = raw.pct_change(252).shift(21)

    # --- Value factor proxy ---
    # Proxy: negative of 1-year return (mean-reversion tilt)
    val_signal = -raw.pct_change(252).shift(21)

    daily_returns = raw.pct_change()

    factor_returns = []

    for date in daily_returns.index[-300:]:
        if date not in mom_signal.index:
            continue
        mom = mom_signal.loc[date].dropna()
        val = val_signal.loc[date].dropna()
        rets = daily_returns.loc[date].dropna()

        common = mom.index.intersection(val.index).intersection(rets.index)
        if len(common) < 20:
            continue

        mom_sorted = mom.loc[common].rank(ascending=False)
        val_sorted = val.loc[common].rank(ascending=False)

        n = len(common)
        top_n = max(10, n // 5)

        mom_long = common[mom_sorted <= top_n]
        mom_short = common[mom_sorted >= (n - top_n + 1)]
        val_long = common[val_sorted <= top_n]
        val_short = common[val_sorted >= (n - top_n + 1)]

        mom_ret = rets.loc[mom_long].mean() - rets.loc[mom_short].mean()
        val_ret = rets.loc[val_long].mean() - rets.loc[val_short].mean()

        factor_returns.append({"date": date, "momentum": mom_ret, "value": val_ret})

    df = pd.DataFrame(factor_returns).set_index("date")
    return df.dropna()


def corr_to_score(corr: float) -> float:
    """Corr +0.3 -> 100, Corr -0.8 -> 0"""
    score = (corr - (-0.8)) / (0.3 - (-0.8)) * 100
    return float(np.clip(score, 0, 100))


def score(factor_df: pd.DataFrame = None) -> dict:
    if factor_df is None:
        factor_df = build_factor_returns()

    if len(factor_df) < 60:
        return {
            "signal": "Factor Crowding",
            "score": 50.0,
            "rolling_corr": 0.0,
            "detail": "Insufficient data for 60-day rolling correlation",
        }

    rolling_60 = factor_df.iloc[-60:]
    corr = float(rolling_60["momentum"].corr(rolling_60["value"]))
    final_score = corr_to_score(corr)

    crowding = "extreme" if corr < -0.5 else ("elevated" if corr < 0 else "normal")

    return {
        "signal": "Factor Crowding",
        "score": final_score,
        "rolling_corr_60d": corr,
        "crowding_level": crowding,
        "detail": f"Mom/Val 60d corr={corr:.2f} ({crowding} crowding)",
    }


if __name__ == "__main__":
    result = score()
    print(result)

import yfinance as yf
import numpy as np
import pandas as pd


def _strip_tz(s):
    if hasattr(s.index, 'tz') and s.index.tz is not None:
        return s.tz_localize(None)
    return s


def _vix_level_scores(vix):
    scores = pd.Series(index=vix.index, dtype=float)
    for i in range(252, len(vix)):
        window = vix.iloc[i - 252:i]
        current = vix.iloc[i]
        pct_rank = np.sum(window >= current) / len(window)
        s = pct_rank * 100
        if current < 15: s += 5
        if current > 30: s -= 10
        scores.iloc[i] = np.clip(s, 0, 100)
    return scores.dropna()


def _term_structure_scores(vix, vix3m):
    common = vix.index.intersection(vix3m.index)
    ratio = vix.loc[common] / vix3m.loc[common]
    return ((1.15 - ratio) / (1.15 - 0.85) * 100).clip(0, 100)


def _breadth_scores_from_spy(spy):
    sma200 = spy.rolling(200).mean()
    gap_pct = (spy - sma200) / sma200
    breadth_est = (0.55 + gap_pct * 5).clip(0.10, 0.95)
    return ((breadth_est - 0.30) / (0.80 - 0.30) * 100).clip(0, 100)


def _credit_scores(hyg, tlt):
    spread = ((tlt.pct_change() - hyg.pct_change()).rolling(20).mean() * 100)
    z = (spread - spread.rolling(252).mean()) / spread.rolling(252).std()
    return ((-z + 2) / 4 * 100).clip(0, 100)


def _putcall_scores(vix):
    roc_pct = vix.pct_change(21) * 100
    return ((-roc_pct + 50) / 80 * 100).clip(0, 100)


def _crowding_scores_proxy(spy):
    rvol = spy.pct_change().rolling(60).std() * np.sqrt(252) * 100
    return ((30 - rvol) / (30 - 10) * 100).clip(0, 100)


WEIGHTS = {
    "vix_level": 0.25, "term_structure": 0.20, "breadth": 0.20,
    "credit": 0.15, "putcall": 0.10, "crowding": 0.10,
}


def run_backtest(lookback_days=730):
    period = f"{lookback_days + 300}d"
    print("Downloading historical data for backtest...")

    vix_raw   = _strip_tz(yf.Ticker("^VIX").history(period=period)["Close"].dropna())
    vix3m_raw = _strip_tz(yf.Ticker("^VIX3M").history(period=period)["Close"].dropna())
    spy_raw   = _strip_tz(yf.Ticker("SPY").history(period=period)["Close"].dropna())

    hyg_tlt = yf.download(["HYG", "TLT"], period=period, auto_adjust=True, progress=False)["Close"].dropna()
    hyg_raw = _strip_tz(hyg_tlt["HYG"])
    tlt_raw = _strip_tz(hyg_tlt["TLT"])

    s1 = _vix_level_scores(vix_raw)
    s2 = _term_structure_scores(vix_raw, vix3m_raw)
    s3 = _breadth_scores_from_spy(spy_raw)
    s4 = _credit_scores(hyg_raw, tlt_raw)
    s5 = _putcall_scores(vix_raw)
    s6 = _crowding_scores_proxy(spy_raw)

    df = pd.DataFrame({
        "vix_level": s1, "term_structure": s2, "breadth": s3,
        "credit": s4, "putcall": s5, "crowding": s6, "spy_close": spy_raw,
    }).dropna()

    df["composite_score"] = sum(df[k] * w for k, w in WEIGHTS.items())

    def assign_zone(s):
        if s >= 70: return "FULL DEPLOY"
        elif s >= 40: return "REDUCED"
        else: return "DEFENSIVE"

    df["zone"] = df["composite_score"].shift(1).apply(assign_zone)
    df["spy_daily_return"] = df["spy_close"].pct_change()
    return df.iloc[-lookback_days:].dropna()


def zone_performance(df):
    results = []
    for zone in ["FULL DEPLOY", "REDUCED", "DEFENSIVE"]:
        subset = df[df["zone"] == zone]["spy_daily_return"]
        down = subset[subset < 0]
        results.append({
            "Zone": zone,
            "Days": len(subset),
            "Avg Daily Return": f"{subset.mean():.3%}",
            "Avg Annual Return": f"{subset.mean() * 252:.1%}",
            "Win Rate": f"{(subset > 0).mean():.1%}",
            "Avg Drawdown": f"{down.mean():.3%}" if len(down) > 0 else "N/A",
        })
    return pd.DataFrame(results)


if __name__ == "__main__":
    df = run_backtest()
    print(zone_performance(df).to_string(index=False))

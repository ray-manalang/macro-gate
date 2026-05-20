"""
analyst/blender.py
------------------
L3 Score Blender: merges the scanner's quantitative composite score (60%)
with Claude's fundamental score (40%), re-ranks candidates, and flags
any ticker whose rank shifted 3+ positions (green = upgraded, red = downgraded).
"""

from __future__ import annotations

import pandas as pd

QUANT_WEIGHT = 0.60
FUNDAMENTAL_WEIGHT = 0.40
RANK_SHIFT_THRESHOLD = 3


def blend_scores(
    scanner_df: pd.DataFrame,
    fundamental_scores: list[dict],
    quant_col: str = "composite",
    ticker_col: str = "ticker",
) -> pd.DataFrame:
    """
    Merge scanner quant scores with Claude fundamental scores and re-rank.

    Returns DataFrame with original scanner columns plus:
        quant_rank, fundamental_score, blended_score, blended_rank,
        rank_delta, rank_flag ('upgrade' | 'downgrade' | '')
    """
    df = scanner_df.copy()

    df["quant_rank"] = df[quant_col].rank(ascending=False, method="min").astype(int)

    fund_df = pd.DataFrame(fundamental_scores)[
        ["ticker", "composite_fundamental_score"]
    ].rename(columns={"composite_fundamental_score": "fundamental_score"})

    df = df.merge(fund_df, left_on=ticker_col, right_on="ticker", how="left")

    if "ticker_y" in df.columns:
        df = df.drop(columns=["ticker_y"]).rename(columns={"ticker_x": ticker_col})

    def norm(series: pd.Series) -> pd.Series:
        mn, mx = series.min(), series.max()
        if mx == mn:
            return pd.Series([0.5] * len(series), index=series.index)
        return (series - mn) / (mx - mn)

    df["quant_norm"] = norm(df[quant_col].fillna(0))
    df["fund_norm"]  = norm(df["fundamental_score"].fillna(df["fundamental_score"].median()))

    df["blended_score"] = (
        QUANT_WEIGHT * df["quant_norm"] +
        FUNDAMENTAL_WEIGHT * df["fund_norm"]
    ).round(4)

    df["blended_rank"] = df["blended_score"].rank(ascending=False, method="min").astype(int)

    df["rank_delta"] = df["quant_rank"] - df["blended_rank"]

    def _flag(delta: int) -> str:
        if delta >= RANK_SHIFT_THRESHOLD:
            return "upgrade"
        if delta <= -RANK_SHIFT_THRESHOLD:
            return "downgrade"
        return ""

    df["rank_flag"] = df["rank_delta"].apply(_flag)

    df = df.sort_values("blended_rank").reset_index(drop=True)
    df = df.drop(columns=["quant_norm", "fund_norm"], errors="ignore")

    return df


def get_flagged(blended_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    upgrades   = blended_df[blended_df["rank_flag"] == "upgrade"].copy()
    downgrades = blended_df[blended_df["rank_flag"] == "downgrade"].copy()
    return {"upgrades": upgrades, "downgrades": downgrades}


def blend_summary(blended_df: pd.DataFrame) -> dict:
    flagged = get_flagged(blended_df)
    return {
        "total_candidates":  len(blended_df),
        "upgraded_count":    len(flagged["upgrades"]),
        "downgraded_count":  len(flagged["downgrades"]),
        "avg_blended_score": round(blended_df["blended_score"].mean(), 3),
        "top_5_tickers":     blended_df.head(5)["ticker"].tolist()
            if "ticker" in blended_df.columns else [],
    }

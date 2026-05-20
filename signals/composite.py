"""
Composite Score
Weighted blend of all 6 signals.
Weights: VIX Level 0.25, Term Structure 0.20, Breadth 0.20,
         Credit 0.15, Put/Call 0.10, Crowding 0.10.

Zones:
  70-100: FULL DEPLOY (100% sizing)
  40-69:  REDUCED (60% sizing)
   0-39:  DEFENSIVE (25% sizing, no new longs)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

WEIGHTS = {
    "VIX Level": 0.25,
    "VIX Term Structure": 0.20,
    "Market Breadth": 0.20,
    "Credit Spreads": 0.15,
    "Put/Call Sentiment": 0.10,
    "Factor Crowding": 0.10,
}

ZONE_THRESHOLDS = {
    "FULL DEPLOY": (70, 100),
    "REDUCED": (40, 69),
    "DEFENSIVE": (0, 39),
}


@dataclass
class DeploymentZone:
    name: str
    sizing: int      # percentage
    color: str       # hex
    new_longs: bool
    scanner: bool


ZONES = {
    "FULL DEPLOY": DeploymentZone("FULL DEPLOY", 100, "#00ff88", True, True),
    "REDUCED":     DeploymentZone("REDUCED",     60,  "#ffaa00", True, True),
    "DEFENSIVE":   DeploymentZone("DEFENSIVE",   25,  "#ff4444", False, False),
}


def get_zone(composite: float) -> DeploymentZone:
    if composite >= 70:
        return ZONES["FULL DEPLOY"]
    elif composite >= 40:
        return ZONES["REDUCED"]
    else:
        return ZONES["DEFENSIVE"]


def compute(signal_results: list[dict]) -> dict:
    """
    Args:
        signal_results: list of dicts, each with 'signal' and 'score' keys.
    Returns:
        composite dict with score, zone, sizing, and per-signal breakdown.
    """
    scores_by_name = {r["signal"]: r["score"] for r in signal_results}

    weighted_sum = 0.0
    total_weight = 0.0
    breakdown = []

    for name, weight in WEIGHTS.items():
        s = scores_by_name.get(name, None)
        if s is not None:
            weighted_sum += s * weight
            total_weight += weight
            breakdown.append({
                "signal": name,
                "score": s,
                "weight": weight,
                "contribution": s * weight,
            })

    composite = weighted_sum / total_weight if total_weight > 0 else 50.0
    zone = get_zone(composite)

    return {
        "composite_score": composite,
        "zone": zone.name,
        "sizing_pct": zone.sizing,
        "zone_color": zone.color,
        "new_longs": zone.new_longs,
        "scanner_active": zone.scanner,
        "breakdown": breakdown,
        "weights_used": WEIGHTS,
    }


if __name__ == "__main__":
    # Quick test with dummy scores
    dummy = [
        {"signal": "VIX Level", "score": 72},
        {"signal": "VIX Term Structure", "score": 85},
        {"signal": "Market Breadth", "score": 60},
        {"signal": "Credit Spreads", "score": 78},
        {"signal": "Put/Call Sentiment", "score": 65},
        {"signal": "Factor Crowding", "score": 55},
    ]
    result = compute(dummy)
    print(f"Composite: {result['composite_score']:.1f} | Zone: {result['zone']}")

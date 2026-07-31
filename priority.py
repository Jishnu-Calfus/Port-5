"""
Auto-prioritization: severity x volume x share-negative -> ranked "top N
actions this week." Deterministic math over what aggregations.py already
computed -- reused, not re-queried.
"""
from sqlalchemy.orm import Session

from aggregations import category_volume, sentiment_by_category

# Business-impact weight per severity level -- same static judgment call as
# SEVERITY_MAP in models.py, just turned into a number so it can multiply.
SEVERITY_WEIGHT = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1, "Unclassified": 0}


def compute_priority(session: Session, top_n: int = 3) -> list[dict]:
    volumes = {row["category"]: row for row in category_volume(session)}
    sentiments = {row["category"]: row for row in sentiment_by_category(session)}

    scored = []
    for category, vol_row in volumes.items():
        negative = sentiments.get(category, {"negative": 0})["negative"]
        volume = vol_row["volume"]
        severity = vol_row["severity"]
        severity_weight = SEVERITY_WEIGHT.get(severity, 0)
        share_negative = negative / volume if volume else 0.0

        # Kept as three explicit factors (not collapsed to severity_weight *
        # negative_count) so the dashboard can show *why* something ranked
        # high -- small-but-severe-and-mostly-negative vs. large-but-mixed.
        score = severity_weight * volume * share_negative

        scored.append({
            "category": category,
            "severity": severity,
            "severity_weight": severity_weight,
            "volume": volume,
            "share_negative": round(share_negative, 2),
            "score": round(score, 1),
        })

    scored.sort(key=lambda row: row["score"], reverse=True)
    return scored[:top_n]

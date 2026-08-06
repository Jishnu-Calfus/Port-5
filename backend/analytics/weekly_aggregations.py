"""
Same aggregation shapes as aggregations.py (category volume, sentiment by
category, source breakdown, daily trend, KPI summary), scoped to the most
recent week of data instead of the whole table -- powers the dashboard's
"This week" view. Row shapes match the all-time versions exactly, so the
same frontend chart components render either dataset unchanged.

"Latest week" is derived from the data's own max timestamp (snapped to that
week's Monday), never from wall-clock "today": this is a batch dataset whose
recency can lag real time (see summary.py's note on the same issue), and it
needs to track whatever the newest loaded data actually is. Loading a batch
that extends past the current latest week's Monday moves this view forward
automatically; loading backfilled older data leaves it untouched, since
`latest_week_bounds` only ever looks at the single most recent timestamp.
"""
from datetime import timedelta

import pandas as pd
from sqlalchemy.orm import Session

from backend.analytics.aggregations import feedback_in_period
from backend.models import FactFeedback


def monday_of(dt):
    return (dt - timedelta(days=dt.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)


def latest_week_bounds(session: Session):
    latest = session.query(FactFeedback.timestamp).order_by(FactFeedback.timestamp.desc()).first()
    if not latest:
        return None, None
    start = monday_of(latest[0])
    return start, start + timedelta(days=7)


def category_volume(records: list[FactFeedback]) -> list[dict]:
    rows = [(cat.name, cat.severity) for r in records for cat in r.categories]
    df = pd.DataFrame(rows, columns=["category", "severity"])
    if df.empty:
        return []
    counts = df.groupby(["category", "severity"], as_index=False).size().rename(columns={"size": "volume"})
    return counts.sort_values("volume", ascending=False).to_dict(orient="records")


def sentiment_by_category(records: list[FactFeedback]) -> list[dict]:
    rows = [(cat.name, r.sentiment.value) for r in records for cat in r.categories]
    df = pd.DataFrame(rows, columns=["category", "sentiment"])
    if df.empty:
        return []
    counts = df.groupby(["category", "sentiment"]).size().unstack(fill_value=0)
    for col in ("negative", "neutral", "positive"):
        if col not in counts.columns:
            counts[col] = 0
    return counts[["negative", "neutral", "positive"]].reset_index().to_dict(orient="records")


def feedback_by_source(records: list[FactFeedback]) -> list[dict]:
    df = pd.DataFrame([{"source": r.source.name} for r in records])
    if df.empty:
        return []
    counts = df.groupby("source", as_index=False).size().rename(columns={"size": "count"})
    return counts.to_dict(orient="records")


def volume_trend(records: list[FactFeedback]) -> list[dict]:
    df = pd.DataFrame([{"timestamp": r.timestamp} for r in records])
    if df.empty:
        return []
    df["date"] = pd.to_datetime(df["timestamp"]).dt.date
    counts = df.groupby("date", as_index=False).size().rename(columns={"size": "count"})
    counts["date"] = counts["date"].astype(str)
    return counts.sort_values("date").to_dict(orient="records")


def kpi_summary(records: list[FactFeedback], categories: list[dict], sentiments: list[dict]) -> dict:
    total = len(records)
    negative = sum(1 for r in records if r.sentiment.value == "negative")
    negative_pct = round(100 * negative / total, 1) if total else 0.0
    top_category = categories[0]["category"] if categories else None

    severity_by_name = {row["category"]: row["severity"] for row in categories}
    critical_open_issues = sum(
        1 for row in sentiments
        if severity_by_name.get(row["category"]) == "Critical" and row["negative"] > 0
    )
    return {
        "total_feedback": total,
        "negative_pct": negative_pct,
        "top_category": top_category,
        "critical_open_issues": critical_open_issues,
    }


def compute_current_week(session: Session) -> dict:
    start, end = latest_week_bounds(session)
    if start is None:
        return {
            "week_start": None, "week_end": None,
            "categories": [], "sentiment": [], "sources": [], "trend": [],
            "kpis": {"total_feedback": 0, "negative_pct": 0.0, "top_category": None, "critical_open_issues": 0},
        }

    records = feedback_in_period(session, start, end)
    categories = category_volume(records)
    sentiments = sentiment_by_category(records)

    return {
        "week_start": start.date().isoformat(),
        "week_end": end.date().isoformat(),
        "categories": categories,
        "sentiment": sentiments,
        "sources": feedback_by_source(records),
        "trend": volume_trend(records),
        "kpis": kpi_summary(records, categories, sentiments),
    }

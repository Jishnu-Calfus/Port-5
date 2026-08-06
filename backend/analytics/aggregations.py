"""
Phase 3: 
-> read-only aggregation queries over the Postgres star schema.
-> one-function per chart/KPI's data need. 
-> Each function pulls joined rows via SQLAlchemy, then does the actual grouping/math with pandas -- the LLM never
touches any of this, matching the project's "deterministic math" principle.
"""
from datetime import datetime

import pandas as pd
from sqlalchemy.orm import Session

from backend.models import DimCategory, DimSource, FactFeedback, FactFeedbackCategory


def feedback_in_period(session: Session, start: datetime, end: datetime) -> list[FactFeedback]:
    """Records in [start, end) -- the scoping primitive the weekly RAG rollup
    (rag_aggregation.py) needs; every other function below still queries the
    full table (fine for the all-time dashboard, not for a period-scoped
    rollup summary)."""
    return (
        session.query(FactFeedback)
        .filter(FactFeedback.timestamp >= start, FactFeedback.timestamp < end)
        .all()
    )


def category_volume(session: Session) -> list[dict]:
    """Per-category feedback count + severity, sorted by volume descending."""
    rows = (
        session.query(DimCategory.name, DimCategory.severity)
        .join(FactFeedbackCategory, FactFeedbackCategory.category_id == DimCategory.id)
        .all()
    )
    df = pd.DataFrame(rows, columns=["category", "severity"])
    counts = df.groupby(["category", "severity"], as_index=False).size().rename(columns={"size": "volume"})
    return counts.sort_values("volume", ascending=False).to_dict(orient="records")


def sentiment_by_category(session: Session) -> list[dict]:
    """Per-category positive/neutral/negative counts, for a diverging stacked bar."""
    rows = (
        session.query(DimCategory.name, FactFeedback.sentiment)
        .join(FactFeedbackCategory, FactFeedbackCategory.category_id == DimCategory.id)
        .join(FactFeedback, FactFeedback.id == FactFeedbackCategory.feedback_id)
        .all()
    )
    df = pd.DataFrame(
        [(cat, s.value if hasattr(s, "value") else s) for cat, s in rows],
        columns=["category", "sentiment"],
    )
    counts = df.groupby(["category", "sentiment"]).size().unstack(fill_value=0)
    for col in ("negative", "neutral", "positive"):
        if col not in counts.columns:
            counts[col] = 0
    return counts[["negative", "neutral", "positive"]].reset_index().to_dict(orient="records")


def feedback_by_source(session: Session) -> list[dict]:
    """Per-source feedback count, for the donut chart."""
    rows = session.query(DimSource.name).join(FactFeedback, FactFeedback.source_id == DimSource.id).all()
    df = pd.DataFrame(rows, columns=["source"])
    counts = df.groupby("source", as_index=False).size().rename(columns={"size": "count"})
    return counts.to_dict(orient="records")


def volume_trend(session: Session) -> list[dict]:
    """Daily feedback count across the dataset's date range, for the line chart."""
    rows = session.query(FactFeedback.timestamp).all()
    df = pd.DataFrame(rows, columns=["timestamp"])
    df["date"] = pd.to_datetime(df["timestamp"]).dt.date
    counts = df.groupby("date", as_index=False).size().rename(columns={"size": "count"})
    counts["date"] = counts["date"].astype(str)
    return counts.sort_values("date").to_dict(orient="records")

#headline numbers 
def kpi_summary(session: Session) -> dict:
    """Headline numbers for the KPI row -- reuses the aggregations above rather
    than re-deriving the same joins/groupings a second time."""
    total = session.query(FactFeedback).count()

    sentiment_rows = session.query(FactFeedback.sentiment).all()
    sentiments = [s[0].value if hasattr(s[0], "value") else s[0] for s in sentiment_rows]
    negative_pct = round(100 * sentiments.count("negative") / total, 1) if total else 0.0

    volumes = category_volume(session)
    top_category = volumes[0]["category"] if volumes else None

    severity_by_name = {row["category"]: row["severity"] for row in volumes}
    sentiment_rows_by_cat = sentiment_by_category(session)
    critical_open_issues = sum(
        1
        for row in sentiment_rows_by_cat
        if severity_by_name.get(row["category"]) == "Critical" and row["negative"] > 0
    )

    return {
        "total_feedback": total,
        "negative_pct": negative_pct,
        "top_category": top_category,
        "critical_open_issues": critical_open_issues,
    }

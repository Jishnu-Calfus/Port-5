"""
Weekly rollup for the RAG knowledge base. Computes the full set of domain
aggregations for one week (scoped via `feedback_in_period`, never the whole
table), renders them into a fixed-shape document, and asks the LLM only for a
short headline/narrative on top of numbers already computed here -- same
sandwich principle as summary.py, the LLM never derives a number itself.

This is what makes the weekly vector count (~52-54/year) durable regardless
of weekly feedback volume: the math is pandas over already-fetched rows, so
it's exact and free whether the week had 10 items or 100,000, and the LLM's
input stays a fixed handful of numbers no matter how much volume they
summarize.
"""
from datetime import datetime

import pandas as pd
from sqlalchemy.orm import Session

from backend.analytics.aggregations import feedback_in_period
from backend.pipeline.llm_client import generate_structured
from backend.models import FactFeedback
from backend.schemas import WeeklyRAGSummary

SEVERITY_WEIGHT = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1, "Unclassified": 0}
TOP_CATEGORIES = 5
QUOTES_PER_CATEGORY = 2

SYSTEM_PROMPT_WEEKLY = """You write a short headline and a 2-3 sentence analysis for one week of \
consumer-fintech user feedback, using ONLY the numbers provided below. Never invent a number, category, \
or example that isn't given to you. If a week-over-week change is provided, call out what's notably \
different from the prior week, not just what's biggest this week."""


def _category_rows(records: list[FactFeedback]) -> pd.DataFrame:
    rows = [
        {"id": r.id, "category": cat.name, "severity": cat.severity, "sentiment": r.sentiment.value}
        for r in records
        for cat in r.categories
    ]
    return pd.DataFrame(rows, columns=["id", "category", "severity", "sentiment"])


def category_breakdown(records: list[FactFeedback]) -> list[dict]:
    """Volume, severity, negative share and a priority score per category --
    ranked by priority (severity x volume x share_negative), not raw volume,
    so a small-but-severe category doesn't get buried under a large-but-mild
    one once weekly volume is large enough to have many candidates."""
    df = _category_rows(records)
    if df.empty:
        return []
    counts = df.groupby(["category", "severity"], as_index=False).size().rename(columns={"size": "volume"})
    negative = df[df["sentiment"] == "negative"].groupby("category").size()
    counts["negative"] = counts["category"].map(negative).fillna(0).astype(int)
    counts["share_negative"] = (counts["negative"] / counts["volume"]).round(2)
    counts["severity_weight"] = counts["severity"].map(SEVERITY_WEIGHT).fillna(0)
    counts["priority_score"] = (counts["severity_weight"] * counts["volume"] * counts["share_negative"]).round(1)
    return counts.sort_values("priority_score", ascending=False).to_dict(orient="records")


def source_breakdown(records: list[FactFeedback]) -> list[dict]:
    df = pd.DataFrame([{"source": r.source.name} for r in records])
    if df.empty:
        return []
    counts = df.groupby("source", as_index=False).size().rename(columns={"size": "count"})
    return counts.sort_values("count", ascending=False).to_dict(orient="records")


def feedback_type_breakdown(records: list[FactFeedback]) -> list[dict]:
    df = pd.DataFrame([{"feedback_type": r.feedback_type.name} for r in records])
    if df.empty:
        return []
    counts = df.groupby("feedback_type", as_index=False).size().rename(columns={"size": "count"})
    return counts.sort_values("count", ascending=False).to_dict(orient="records")


def week_over_week_deltas(current: list[dict], previous: list[dict]) -> list[dict]:
    """Per-category volume % change vs. the prior week -- flags what's moving,
    not just what's biggest, so an emerging spike isn't hidden behind a bigger
    but flat category."""
    prev_volume_by_cat = {row["category"]: row["volume"] for row in previous}
    deltas = []
    for row in current:
        prev_volume = prev_volume_by_cat.get(row["category"], 0)
        pct_change = round(100 * (row["volume"] - prev_volume) / prev_volume, 1) if prev_volume else None
        deltas.append({
            "category": row["category"],
            "volume": row["volume"],
            "prev_volume": prev_volume,
            "pct_change": pct_change,
        })
    return deltas


def representative_quotes(records: list[FactFeedback], categories: list[str], per_category: int = QUOTES_PER_CATEGORY) -> list[dict]:
    """A couple of real, citable quotes per top category -- negative-sentiment
    first (most actionable), falling back to any sentiment if a category has
    no negative examples that week. Kept to a fixed handful per category so
    this doesn't scale with weekly volume."""
    quotes = []
    for cat_name in categories:
        cat_records = [r for r in records if any(c.name == cat_name for c in r.categories)]
        negative = [r for r in cat_records if r.sentiment.value == "negative"]
        pool = negative if negative else cat_records
        for r in pool[:per_category]:
            quotes.append({"id": r.id, "category": cat_name, "quote": r.feedback_text})
    return quotes


def compute_weekly_aggregation(
    session: Session,
    start: datetime,
    end: datetime,
    previous_categories: list[dict] | None = None,
) -> dict:
    records = feedback_in_period(session, start, end)
    categories = category_breakdown(records)
    top_categories = [row["category"] for row in categories[:TOP_CATEGORIES]]

    return {
        "start": start,
        "end": end,
        "total": len(records),
        "categories": categories,
        "sources": source_breakdown(records),
        "feedback_types": feedback_type_breakdown(records),
        "deltas": week_over_week_deltas(categories, previous_categories) if previous_categories is not None else None,
        "quotes": representative_quotes(records, top_categories),
    }


def render_weekly_document(stats: dict, narrative: WeeklyRAGSummary) -> str:
    """Fixed-shape template -- same section order and phrasing scaffolding
    every week, so only the differing content shifts the embedding, not the
    document's structure."""
    lines = [
        f"Week of {stats['start'].date()} to {stats['end'].date()}",
        f"Total feedback: {stats['total']}",
        "",
        "Category breakdown (priority-ranked: severity x volume x negative-share):",
    ]
    for row in stats["categories"][:TOP_CATEGORIES]:
        lines.append(
            f"- {row['category']} (severity={row['severity']}, volume={row['volume']}, "
            f"negative_share={row['share_negative']:.0%}, priority_score={row['priority_score']})"
        )

    if stats["deltas"]:
        lines.append("")
        lines.append("Week-over-week volume change:")
        for row in stats["deltas"]:
            if row["pct_change"] is None:
                lines.append(f"- {row['category']}: new this week ({row['volume']})")
            else:
                sign = "+" if row["pct_change"] >= 0 else ""
                lines.append(
                    f"- {row['category']}: {row['volume']} ({sign}{row['pct_change']}% vs. prior week's {row['prev_volume']})"
                )

    if stats["sources"]:
        lines.append("")
        lines.append("Source breakdown: " + ", ".join(f"{r['source']}={r['count']}" for r in stats["sources"]))
    if stats["feedback_types"]:
        lines.append("Feedback type breakdown: " + ", ".join(f"{r['feedback_type']}={r['count']}" for r in stats["feedback_types"]))

    lines.append("")
    lines.append(f"Headline: {narrative.headline}")
    lines.append(f"Analysis: {narrative.narrative}")

    if stats["quotes"]:
        lines.append("")
        lines.append("Representative examples (supporting color only, not a citation target):")
        for q in stats["quotes"]:
            # Deliberately not "[id=...]" bracket notation -- that shape competes
            # with the outer per-excerpt numbering rag.py's synthesize() uses for
            # citation, and a small model reliably latches onto whichever bracket
            # pattern appears more often (many quotes per week vs. one number per
            # excerpt), citing feedback ids instead of weeks.
            lines.append(f'- {q["category"]}, feedback #{q["id"]}: "{q["quote"]}"')

    return "\n".join(lines)


def narrate_and_render(stats: dict) -> str:
    """Takes already-computed stats (from `compute_weekly_aggregation`) and adds
    the one LLM call for headline/narrative, then renders the final document.
    Split from `compute_weekly_aggregation` so a caller can inspect `total`
    (e.g. skip empty weeks) before paying for the LLM call."""
    stats_lines = [f"Total feedback: {stats['total']}", "Categories (priority-ranked):"]
    for row in stats["categories"][:TOP_CATEGORIES]:
        stats_lines.append(
            f"- {row['category']}: volume={row['volume']}, severity={row['severity']}, negative_share={row['share_negative']:.0%}"
        )
    if stats["deltas"]:
        stats_lines.append("Week-over-week change:")
        for row in stats["deltas"]:
            if row["pct_change"] is not None:
                stats_lines.append(f"- {row['category']}: {row['pct_change']}% change")

    narrative = generate_structured(SYSTEM_PROMPT_WEEKLY, "\n".join(stats_lines), WeeklyRAGSummary)
    return render_weekly_document(stats, narrative)

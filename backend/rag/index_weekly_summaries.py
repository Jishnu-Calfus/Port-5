"""
Builds the RAG knowledge base as one aggregated, fixed-shape document per ISO
week -- replaces per-item raw dumping (index_feedback.py) as the RAG corpus,
so the vector store stays at ~52-54 documents/year regardless of weekly
feedback volume, instead of growing with every raw feedback item.

Run once to backfill every historical week, then re-run weekly (e.g. via
cron) to add just the newest week. Re-running is idempotent: `upsert` deletes
and re-adds by week-start id, so a partial re-run overwrites, it never
duplicates -- as long as week boundaries stay anchored to real calendar weeks
(Monday-start) rather than "whatever the earliest timestamp happens to be in
the current run," which would silently shift the whole grid and orphan
previously-indexed weeks under different ids whenever new data changes what
"earliest" means.
"""
from datetime import timedelta

from backend.db import SessionLocal
from backend.models import FactFeedback
from backend.rag.rag_aggregation import compute_weekly_aggregation, narrate_and_render
from backend.rag.vector_store import weekly_collection
from backend.analytics.weekly_aggregations import monday_of


def week_starts(first, last):
    current = first
    while current < last:
        yield current
        current += timedelta(days=7)


def index_weekly_summaries() -> None:
    session = SessionLocal()
    try:
        earliest = session.query(FactFeedback.timestamp).order_by(FactFeedback.timestamp.asc()).first()
        latest = session.query(FactFeedback.timestamp).order_by(FactFeedback.timestamp.desc()).first()
        if not earliest:
            print("No feedback data to index.")
            return

        start = monday_of(earliest[0])
        end = latest[0]

        previous_categories = None
        for week_start in week_starts(start, end + timedelta(days=7)):
            week_end = week_start + timedelta(days=7)
            stats = compute_weekly_aggregation(session, week_start, week_end, previous_categories)

            # Skip weeks with no records entirely -- nothing to narrate, and an
            # empty-stats LLM call has nothing grounded to say (it hallucinates
            # instead), so don't call it or embed a vector for it. Don't advance
            # `previous_categories` past a skipped week either, so the next
            # real week's delta still compares against the last real baseline.
            if stats["total"] == 0:
                print(f"Skipping week {week_start.date().isoformat()}: no feedback items")
                continue
            previous_categories = stats["categories"]

            document = narrate_and_render(stats)
            week_id = week_start.date().isoformat()
            weekly_collection.upsert(
                ids=[week_id],
                documents=[document],
                metadatas=[{
                    "week_start": week_start.date().isoformat(),
                    "week_end": week_end.date().isoformat(),
                    "total_feedback": stats["total"],
                }],
            )
            print(f"Indexed week {week_id}: {stats['total']} feedback items")
    finally:
        session.close()


if __name__ == "__main__":
    index_weekly_summaries()

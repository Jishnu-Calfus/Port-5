"""
Phase 2: load feedback_enriched.json into the Postgres star schema.

Full rebuild each run (drop + recreate + reload) — the enriched JSON is the
source of truth and the dataset is small, so this is simpler and safer than
tracking incremental upserts.
"""
import json
from datetime import datetime

from sqlalchemy.orm import Session

from config import ENRICHED_DIR
from db import Base, SessionLocal, engine
from models import SEVERITY_MAP, DimCategory, DimFeedbackType, DimSource, FactFeedback, FactFeedbackCategory
from schemas import EnrichedData, FeedbackType, Source, Topic


def load_enriched() -> list[EnrichedData]:
    with open(f"{ENRICHED_DIR}/feedback_enriched.json") as f:
        rows = json.load(f)
    return [EnrichedData.model_validate(r) for r in rows]


def seed_dims(session: Session) -> tuple[dict, dict, dict]:
    """All three dimensions come from fixed enum values, not from the data itself —
    unlike the old dim_date, nothing here needs the actual records."""
    source_by_name = {}
    for s in Source:
        obj = DimSource(name=s.value)
        session.add(obj)
        source_by_name[s.value] = obj

    feedback_type_by_name = {}
    for ft in FeedbackType:
        obj = DimFeedbackType(name=ft.value)
        session.add(obj)
        feedback_type_by_name[ft.value] = obj

    category_by_name = {}
    for t in Topic:
        obj = DimCategory(name=t.value, severity=SEVERITY_MAP[t.value])
        session.add(obj)
        category_by_name[t.value] = obj

    session.flush()  # assign PKs without committing yet
    return source_by_name, feedback_type_by_name, category_by_name


def load_facts(session: Session, records: list[EnrichedData], source_by_name, feedback_type_by_name, category_by_name):
    for r in records:
        ts = datetime.fromisoformat(r.timestamp.replace("Z", "+00:00"))
        fact = FactFeedback(
            id=r.id,
            source_id=source_by_name[r.source.value].id,
            feedback_type_id=feedback_type_by_name[r.feedback_type.value].id,
            sentiment=r.sentiment,
            feedback_text=r.feedback,
            timestamp=ts,
        )
        session.add(fact)
        session.flush()  # need fact.id resolvable before bridge rows reference it

        for topic in r.category:
            session.add(FactFeedbackCategory(feedback_id=fact.id, category_id=category_by_name[topic.value].id))


def main():
    records = load_enriched()

    # Full rebuild: drop and recreate so re-running is always safe/idempotent.
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        #unpacking seed_dims return values into three separate tuples
        source_by_name, feedback_type_by_name, category_by_name = seed_dims(session)

        #loading steps into the fact tables using the enriched records and the dimension mappings
        load_facts(session, records, source_by_name, feedback_type_by_name, category_by_name)
        session.commit()

    print(f"Loaded {len(records)} feedback records into Postgres "
          f"({len(feedback_type_by_name)} feedback types, {len(category_by_name)} categories).")


if __name__ == "__main__":
    main()

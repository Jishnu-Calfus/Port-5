"""
Phase 1 classification: read feedback_staging, classify each record with the
local LLM (temp=0, few-shot, JSON-schema-constrained), validate, and merge
into feedback_enriched. This is the end of Phase 1 — enriched data is the
deliverable; aggregation/dashboarding happens in later phases.
"""
import json

import pandas as pd

from backend.config import STAGING_DIR, ENRICHED_DIR
from backend.pipeline.llm_client import generate_structured, LLMOutputError
from backend.pipeline.prompts import build_system_prompt, build_user_prompt
from backend.schemas import Classification, EnrichedData

SYSTEM_PROMPT = build_system_prompt()


def classify_one(feedback_text: str) -> Classification:
    user_prompt = build_user_prompt(feedback_text)
    return generate_structured(SYSTEM_PROMPT, user_prompt, Classification)


def build_enriched() -> list[EnrichedData]:
    staging = pd.read_csv(f"{STAGING_DIR}/feedback_staging.csv")

    enriched: list[EnrichedData] = []
    failures: list[dict] = []

    for i, row in enumerate(staging.to_dict(orient="records"), start=1):
        try:
            classification = classify_one(row["feedback"])
        except LLMOutputError as exc:
            failures.append({"id": row["id"], "error": str(exc)})
            print(f"[{i}/{len(staging)}] id={row['id']} FAILED: {exc}")
            continue

        record = EnrichedData(
            id=row["id"],
            timestamp=row["timestamp"],
            source=row["source"],
            feedback=row["feedback"],
            category=classification.category,
            feedback_type=classification.feedback_type,
            sentiment=classification.sentiment,
        )
        enriched.append(record)
        # loop-logging 
        print(f"[{i}/{len(staging)}] id={row['id']} -> "
              f"{[c.value for c in classification.category]} / "
              f"{classification.feedback_type.value} / {classification.sentiment.value}")

    if failures:
        print(f"\n{len(failures)} record(s) failed classification and were skipped:")
        for f in failures:
            print(f"  id={f['id']}: {f['error']}")

    return enriched


def main():
    enriched = build_enriched()
    out_path = f"{ENRICHED_DIR}/feedback_enriched.json"
    with open(out_path, "w") as f:
        json.dump([r.model_dump(mode="json") for r in enriched], f, indent=2)
    print(f"\nWrote {len(enriched)} enriched records to {out_path}")


if __name__ == "__main__":
    main()

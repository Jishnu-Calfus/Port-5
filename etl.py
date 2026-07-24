"""
Phase 1 ETL: normalize the three raw feedback sources (app-store reviews,
support tickets, survey responses) into one flat feedback_staging table.

Raw -> normalized only. No classification happens here — that's classify.py.
"""
import json

import pandas as pd

from config import RAW_DIR, STAGING_DIR
from schemas import Source, StagingRecord


def _load_reviews() -> pd.DataFrame:
    with open(f"{RAW_DIR}/reviews.json") as f:
        rows = json.load(f)
    df = pd.DataFrame(rows)
    df["feedback"] = df["text"]
    df["timestamp"] = pd.to_datetime(df["date"]).dt.tz_localize("UTC")
    df["source"] = Source.Reviews.value
    return df[["feedback", "timestamp", "source"]]


def _load_tickets() -> pd.DataFrame:
    df = pd.read_csv(f"{RAW_DIR}/tickets.csv")
    df["feedback"] = df["subject"].str.strip() + ": " + df["message"].str.strip()
    df["timestamp"] = pd.to_datetime(df["created_at"]).dt.tz_localize("UTC")
    df["source"] = Source.Tickets.value
    return df[["feedback", "timestamp", "source"]]


def _load_surveys() -> pd.DataFrame:
    df = pd.read_csv(f"{RAW_DIR}/surveys.csv")
    df["feedback"] = df["response"].str.strip()
    df["timestamp"] = pd.to_datetime(df["submitted_at"]).dt.tz_localize("UTC")
    df["source"] = Source.Survey.value
    return df[["feedback", "timestamp", "source"]]


def build_staging() -> pd.DataFrame:
    combined = pd.concat(
        [_load_reviews(), _load_tickets(), _load_surveys()],
        ignore_index=True,
    )
    # Remove empty feedback and duplicates (ex: the same survey response might be in both the survey and ticket sources).
    combined["feedback"] = combined["feedback"].str.strip()
    combined = combined[combined["feedback"].str.len() > 0]
    combined = combined.drop_duplicates(subset="feedback")

    combined = combined.sort_values("timestamp").reset_index(drop=True)
    combined.insert(0, "id", combined.index + 1)
    combined["timestamp"] = combined["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    #List of dicts convertion using this to_dict(orient="records") method and then validating each row using StagingRecord.model_validate(row) to ensure that the data adheres to the defined schema.
    for row in combined.to_dict(orient="records"):
        StagingRecord.model_validate(row)

    return combined


def main():
    staging = build_staging()
    out_path = f"{STAGING_DIR}/feedback_staging.csv"
    staging.to_csv(out_path, index=False)
    print(f"Wrote {len(staging)} normalized records to {out_path}")


if __name__ == "__main__":
    main()

# PulseAI

An AI-powered pipeline that ingests consumer-fintech feedback (app-store reviews,
support tickets, survey responses), classifies it against a fixed taxonomy with
sentiment, and produces enriched, structured records ready for aggregation and
reporting.

**Phase 1 (this state of the repo):** raw sources → normalized staging → LLM
classification (few-shot, temp=0, schema-validated) → enriched data. Later
phases (data modeling, vector store / RAG / priority scoring, dashboard) build
on top of `data/enriched/feedback_enriched.json`.

## Architecture

```
data/raw/{reviews.json, tickets.csv, surveys.csv}   raw sources, kept as-is
        │  etl.py: normalize + dedupe + drop empties
        ▼
data/staging/feedback_staging.csv                   flat {id, source, feedback, timestamp}
        │  classify.py: LLM classify (temp=0, few-shot, JSON-schema output) + validate
        ▼
data/enriched/feedback_enriched.json                staging fields + {category, feedback_type, sentiment}
```

The LLM only ever produces the three enriched fields (`category`,
`feedback_type`, `sentiment`) — everything else (`id`, `timestamp`, `source`,
`feedback`) is carried over from staging in code. This keeps the model's job
narrow and its output deterministic and easy to validate.

## Setup

1. Install [Ollama](https://ollama.com) and pull the model used for classification:
   ```
   ollama pull qwen2.5:7b-instruct
   ```
2. Start the Ollama server (skip if the desktop app is already running):
   ```
   ollama serve
   ```
3. Install Python deps:
   ```
   uv sync
   ```
4. Copy `.env.example` to `.env` (defaults already point at a local Ollama):
   ```
   cp .env.example .env
   ```

## Run

```
uv run main.py
```

This runs ETL then classification end-to-end and writes:
- `data/staging/feedback_staging.csv`
- `data/enriched/feedback_enriched.json`

To run either stage independently: `uv run etl.py` / `uv run classify.py`.

## Taxonomy

12 topic categories (multi-label), a 6-value `feedback_type` (bug / complaint /
feature_request / question / churn_risk / praise), and 3-value `sentiment`
(positive / neutral / negative). Full definitions and boundary rules live in
`prompts.py` alongside the few-shot examples that teach the model where each
category's edges are.

## Data

`data/raw/reviews.json` is a curated, paraphrased sample standing in for real
app-store reviews (a real scraped/exported set can be dropped in with the same
shape later). `tickets.csv` and `surveys.csv` are synthesized to resemble the
language patterns seen in real fintech support tickets and survey responses,
per the project's data-sourcing guidance — never synthesized to artificially
inflate classification accuracy.

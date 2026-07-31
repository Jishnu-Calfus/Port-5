# PulseAI

An AI-powered pipeline that ingests consumer-fintech feedback (app-store reviews,
support tickets, survey responses), classifies it against a fixed taxonomy with
sentiment, and produces enriched, structured records ready for aggregation and
reporting.

**Phase 1:** raw sources → normalized staging → LLM classification (few-shot,
temp=0, schema-validated) → enriched data (`feedback_enriched.json`).
**Phase 2:** that JSON loaded into a proper Postgres star schema for real
aggregation. **Phase 3 (this state of the repo):** priority scoring, a
grounded weekly narrative summary, a RAG "ask your feedback" pipeline
(ChromaDB + Ollama), and a FastAPI layer wrapping all of it. **Phase 4:** a
React dashboard consuming that API.

## Architecture

```
data/raw/{reviews.json, tickets.csv, surveys.csv}   raw sources, kept as-is
        │  etl.py: normalize + dedupe + drop empties
        ▼
data/staging/feedback_staging.csv                   flat {id, source, feedback, timestamp}
        │  classify.py: LLM classify (temp=0, few-shot, JSON-schema output) + validate
        ▼
data/enriched/feedback_enriched.json                staging fields + {category, feedback_type, sentiment}
        │  model.py: seed dimensions, explode multi-label category into a bridge table
        ▼
Postgres star schema (pulseai db)                   fact_feedback + dim_source/feedback_type/category
        │                                    │
        │  aggregations.py, priority.py,     │  index_feedback.py: pull from Postgres,
        │  summary.py                        │  embed (nomic-embed-text), load into Chroma
        ▼                                    ▼
api.py (FastAPI)  ◄──────────────────  rag.py (retrieve + synthesize)
        │
        ▼
frontend/ (Vite + React) -- fetches api.py's endpoints, renders the dashboard
```

The LLM only ever produces the three enriched fields (`category`,
`feedback_type`, `sentiment`) — everything else (`id`, `timestamp`, `source`,
`feedback`) is carried over from staging in code. This keeps the model's job
narrow and its output deterministic and easy to validate.

## Data model (Phase 2)

**A full ER diagram of the star schema below is in [`data_model.md`](data_model.md)** —
renders directly on GitHub, no extra tooling needed.

`feedback_enriched.json` is a convenient checkpoint, not an analytical format —
`category` is a list, so it can't be grouped/aggregated directly. `model.py`
loads it into a small star schema in Postgres (`models.py`, SQLAlchemy ORM):

- **`fact_feedback`** — grain is one row per feedback item: `sentiment`
  (native Postgres enum), `feedback_text`, `timestamp`, plus FKs to
  `dim_source` and `dim_feedback_type`.
- **`dim_source`** / **`dim_feedback_type`** — small reference tables for the
  3 sources and 6 feedback types; `fact_feedback` links to each with a plain
  foreign key since every feedback item has exactly one of each.
- **`dim_category`** — the 12 taxonomy topics, each with a static `severity`
  (Critical/High/Medium/Low/Unclassified) hardcoded in `models.py` — severity
  is a business-impact judgment call, never something the LLM decides or
  something derived from the data.
- **`fact_feedback_category`** — a bridge table: since one feedback item can
  have multiple categories, a plain FK column on `fact_feedback` can't
  represent it (a column only holds one value). This many-to-many join table
  between `fact_feedback` and `dim_category` (the standard pattern for a
  multi-valued dimension) keeps `fact_feedback`'s grain unambiguous — exactly
  one row per feedback item, never duplicated per category.

`model.py` does a full drop/recreate/reload each run — the enriched JSON is
the source of truth and the dataset is small, so "rebuild the warehouse from
scratch" is simpler than tracking incremental upserts.

## Intelligence layer (Phase 3)

Built on top of the star schema, not the JSON:

- **`aggregations.py`** — read-only queries for every chart/KPI (category
  volume, sentiment-by-category, source breakdown, volume trend, headline
  KPI numbers). Pandas does the grouping/math; nothing here touches the LLM.
- **`priority.py`** — `severity × volume × share-negative` → ranked top
  actions, all three factors kept visible (not collapsed into one number) so
  the ranking is explainable, not just a black-box score.
- **`summary.py`** — an LLM narrates a short weekly summary, but only from
  numbers `aggregations.py`/`priority.py` already computed — it's never
  handed raw data to re-derive numbers from itself.
- **`vector_store.py` / `index_feedback.py` / `rag.py`** — a separate,
  parallel path: feedback text gets embedded (Ollama's `nomic-embed-text`)
  and indexed into **ChromaDB**, a persistent, embedded (no server process)
  vector store living at `data/chroma/`. `rag.py`'s `ask()` embeds a
  question, retrieves the most semantically similar feedback, and has the
  LLM synthesize a cited answer — grounded only in what was retrieved, never
  invented. Important limitation: this is semantic *search*, not a database
  filter — "give me every item in category X" is a job for Postgres/
  `aggregations.py`, not the RAG box, which only guarantees the top-k most
  *similar* results to the question's exact wording, not an exhaustive list.
- **`api.py`** — a FastAPI layer wrapping all of the above as JSON endpoints
  (`/api/kpis`, `/api/priority`, `/api/categories`, `/api/sentiment`,
  `/api/sources`, `/api/trend`, `/api/summary`, `POST /api/ask`), with CORS
  enabled for the frontend's dev server.

## Dashboard (Phase 4)

`frontend/` — Vite + plain React (no Next.js), fetching `api.py`'s endpoints
and rendering: a KPI row, the priority panel, four charts (category volume
bar, sentiment diverging stacked bar, source donut, volume trend line), the
"ask your feedback" RAG box, and the weekly summary — in that order, top to
bottom. Dark theme and chart-type choices are sourced from a validated
color/chart-form design system rather than picked by eye (see `theme.css`).

## Setup

1. Install [Ollama](https://ollama.com) and pull both models used (one for
   classification/synthesis, one for embeddings):
   ```
   ollama pull qwen2.5:7b-instruct
   ollama pull nomic-embed-text
   ```
2. Start the Ollama server (skip if the desktop app is already running):
   ```
   ollama serve
   ```
3. Install Python deps:
   ```
   uv sync
   ```
4. Copy `.env.example` to `.env` (defaults already point at a local Ollama + Postgres):
   ```
   cp .env.example .env
   ```
5. Install [Postgres.app](https://postgresapp.com) (native macOS app, no Homebrew
   needed), then create a data directory and start the server once:
   ```
   PGBIN=/Applications/Postgres.app/Contents/Versions/16/bin
   "$PGBIN/initdb" -D ~/postgres-data/pulseai -U "$USER" -A trust --encoding=UTF8
   "$PGBIN/pg_ctl" -D ~/postgres-data/pulseai -l ~/postgres-data/pulseai.log -o "-p 5432" start
   "$PGBIN/createuser" pulseai --createdb
   "$PGBIN/psql" -d postgres -c "ALTER ROLE pulseai WITH PASSWORD 'pulseai';"
   "$PGBIN/createdb" -O pulseai pulseai
   ```
   On future sessions you only need the `pg_ctl ... start` line (or `... stop` to shut it down).
6. Install [Node.js](https://nodejs.org) (LTS) for the frontend -- easiest via
   [nvm](https://github.com/nvm-sh/nvm), no Homebrew/sudo needed:
   ```
   curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
   nvm install --lts
   ```
7. Install frontend deps:
   ```
   cd frontend && npm install
   ```

## Run

Backend pipeline (run once, or whenever the raw data changes):
```
uv run main.py             # Phase 1: ETL -> LLM classification -> feedback_enriched.json
uv run model.py             # Phase 2: load feedback_enriched.json into the Postgres star schema
uv run index_feedback.py    # Phase 3: embed feedback into ChromaDB for RAG
```

Then, in two separate terminals, run the API and the dashboard together:
```
uv run uvicorn api:app --host 127.0.0.1 --port 8000 --reload   # backend API, http://127.0.0.1:8000
cd frontend && npm run dev                                       # dashboard, http://localhost:5173
```
`--reload` matters -- without it, uvicorn loads `api.py` once at startup and
won't notice later edits to any backend file until manually restarted.

To run any single stage independently: `uv run etl.py` / `uv run classify.py` /
`uv run model.py` / `uv run index_feedback.py`.

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

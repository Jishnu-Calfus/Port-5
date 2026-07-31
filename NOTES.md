# Build Notes

Running log of decisions, surprises, and things to revisit. Started at Phase 1.

## 2026-07-23 — Phase 1: ETL + classification to enriched data

**What got built:** `etl.py` (normalize 3 raw sources into `feedback_staging`),
`prompts.py` (taxonomy + few-shot system prompt), `llm_client.py` (Ollama
wrapper: temp=0, JSON-schema-constrained output, validate + retry), `classify.py`
(staging → enriched), `main.py` (orchestrates both).

**Environment:** local Ollama (`qwen2.5:7b-instruct`), no API key needed —
chosen over a cloud API to keep this fully local/free. Determinism was
verified directly: same input classified 3x at temp=0 produced byte-identical
output.

**Surprise / gap found in the schema:** the original `feedback_type` enum
(bug / complaint / feature_request / question / churn_risk) had no value for
positive feedback with no ask attached — every positive review was getting
force-labeled `complaint`, which reads as contradictory next to
`sentiment: positive` in the enriched data. Added a `praise` value. Good
reminder that `sentiment` (tone) and `feedback_type` (intent) need to be
checked for consistency as a pair, not just validated individually against
the schema — schema-valid isn't the same as *coherent*.

**Few-shot design:** rather than one example per category, examples were
picked to sit on category *boundaries* — e.g. "account frozen by the company"
vs. "account taken over by a fraudster" (both look like "I can't access my
money" on the surface, but one is Account Access & Freezes and the other is
Fraud & Security). Same idea for Transfers & Payments vs. Fees & Pricing (a
transfer fee complaint isn't a transfer-mechanics complaint) and App
Performance vs. Usability (broken vs. merely confusing). This is the concrete
answer to "why few-shot over zero-shot" — it's not about format compliance,
it's about teaching the boundary the taxonomy actually cares about.

**Data sourcing:** `reviews.json` is a curated, paraphrased sample (not
scraped) standing in for real app-store reviews for now — real reviews can
replace it later with the same shape. Tickets/surveys are synthesized to
match observed complaint language, per the project's own rule not to
synthesize data in a way that would inflate accuracy against the taxonomy.

**What I'd revisit:** no accuracy harness yet (holding out labeled blind
inputs and scoring against them) — that's needed before trusting the 30%
mission-specific rubric line, and multi-label + boundary cases (like the
churn_risk example that's *also* an Account Access & Freezes complaint) are
exactly where I'd expect disagreement between the model and a human labeler.

## 2026-07-24 — Phase 2: data modeling (Postgres + SQLAlchemy)

**What got built:** `models.py` (star schema: `dim_source`, `dim_feedback_type`,
`dim_category` with severity, `fact_feedback`, `fact_feedback_category` bridge),
`model.py` (loads `feedback_enriched.json` into it, full rebuild each run),
`db.py` (SQLAlchemy engine/session).

**Environment:** Postgres.app installed natively (no Docker, no Homebrew —
downloaded the dmg, verified it with `hdiutil attach`, drove its bundled
`initdb`/`pg_ctl` directly from the CLI instead of the GUI onboarding wizard).

**Schema is 3 dimensions, not the original 3+date:** the first pass at this
schema used `source`/`category`/`date` as dimensions. Redesigned around
`source`/`category`/`feedback_type` instead — dropping the date dimension
(timestamp stays a plain column on the fact table) and promoting
`feedback_type` from an inline enum column to its own small reference table.
Worth noting neither design is "more correct" — which fields deserve to be
dimensions is a modeling choice, not a fact about the data.

**Severity is hardcoded, not calculated:** it's a business-impact judgment
call (e.g. Account Access & Freezes = Critical, Usability & UX = Low),
completely independent of frequency or sentiment — a category with only 2
complaints can matter more than one with 50. No formula derives that; it's a
fixed lookup applied once in `models.py`, same treatment as the taxonomy
itself.

**Only `category` needed a bridge table:** `source` and `feedback_type` are
single-valued per feedback item, so they're plain FK columns on
`fact_feedback` — same as any normal one-to-many relationship. `category` is
multi-label, so a single FK column can't represent it (a column holds one
value; some feedback items need 2+). The alternative — one `fact_feedback` row
per category — would break `id` as a unique identifier and make
`count(*) FROM fact_feedback` lie about how many feedback items actually
exist. The bridge table (`fact_feedback_category`) is the standard relational
answer to "many-to-many without corrupting the fact table's grain": 56
feedback items produced 66 bridge rows, the exact number of category labels
across all of them.

**Gotcha: `drop_all`/`create_all` only manage tables currently defined in
Python.** After redesigning away from a `dim_date` table, the old `dim_date`
table stayed behind in Postgres — `Base.metadata.drop_all()` only knows about
tables registered on `Base.metadata` *right now*, so a table whose class got
deleted from `models.py` becomes orphaned, invisible to both `drop_all` and
`create_all`, until someone drops it manually.

**Course correction (carried over from the first Phase 2 attempt):** first
instinct was to spin up Postgres in Docker since Docker was already on the
machine — got called out for reaching for it without being asked. Backed out
and installed Postgres.app natively instead. Lesson: default to the
lightest-touch option that does what was actually asked, not what's most
convenient to reach for.

## 2026-07-30 — Phase 3: intelligence layer (priority, RAG, weekly summary, API)

**What got built:** `aggregations.py` (chart/KPI queries), `priority.py`
(`severity x volume x share-negative` ranking), `summary.py` + a
`WeeklySummary` schema (narrative grounded in the two above), `vector_store.py`
/ `index_feedback.py` / `rag.py` (ChromaDB + Ollama embeddings for "ask your
feedback"), `api.py` (FastAPI wrapping all of it).

**Priority score is kept as 3 explicit factors, not collapsed:**
`severity_weight x volume x share_negative` could be simplified to
`severity_weight x negative_count` (since `volume x share_negative` literally
*is* the negative count) — mathematically identical, but collapsing it would
hide *why* a category ranked where it did. Keeping all three visible answers
"is this high-priority because it's small-but-severe-and-mostly-negative, or
large-with-a-smaller-negative-share?" without extra work.

**ChromaDB needed no server at all, unlike Postgres** — it's an embedded
database: the engine is a library linked into whatever script imports it,
reading/writing its own files straight to `data/chroma/`. Proved this
concretely: wrote one document from one Python process, then read it back
from a completely separate process afterward with nothing running in
between — same idea as SQLite, just for vectors.

**RAG is semantic search, not a database filter — this bit us for real.** Asked
"give me all reviews in the Fees & Pricing category, in order" — Postgres
says there are 4 (`id=24,32,33,34`); the RAG box only surfaced 3 (`24,33,32`),
and pulled in two *unrelated* items (about app crashes and the UI redesign)
along the way. Root cause: `retrieve()` embeds the whole question and finds
the k nearest neighbors by similarity — there's no category filter at all, so
a long, meta-heavy question phrasing ("give me a detailed report... in
order") shifted the embedding enough that the genuine 4th item fell outside
the top-k while two irrelevant ones ranked closer. The LLM actually behaved
correctly given what it was shown (it didn't hallucinate the missing one, and
correctly ignored the two irrelevant retrieved items) — the gap was upstream,
in retrieval, not generation. Lesson: "give me every item matching X" is
always a job for the structured store (`aggregations.py`/Postgres), never the
vector search box, no matter how the question is phrased.

**Dropped Next.js for plain React** partway into planning Phase 4, on
direction: Next.js's App Router adds real conceptual overhead (server vs.
client components) on top of learning React itself, and the ask was for
something minimal, not a framework-scale build. Vite + React + Recharts talks
to `api.py` over plain fetch — no SSR, no framework routing, one page.

**Design system wasn't hand-picked** — sourced from a validated
color/chart-form methodology (CVD-safe categorical palette, chart-type rules
per data job) rather than choosing colors/chart types by eye. Concretely: the
sentiment chart is a diverging stacked bar, not a pie, because sentiment is
*ordered* (negative↔positive) and a pie would destroy that ordering; the
source breakdown *is* a donut because those 3 categories are genuinely
unordered.

**Gotcha: `uvicorn` without `--reload` silently serves stale code.** Changed
`top_n=3` to `top_n=4` in `api.py`, hit the endpoint, still got 3 back —
because the server process had `api.py`'s old code loaded into memory from
when it started, and nothing was watching the file for changes. `--reload`
is the flag that makes uvicorn notice edits automatically; without it, a
manual restart is required every time, and it's easy to mistake "my change
didn't work" for a real bug when it's actually just a stale process.

**What I'd revisit:** no automated accuracy harness or edge-case/API-failure
robustness testing yet (empty input, wrong-language input, Ollama being
unreachable mid-batch) — both called out explicitly in the original brief and
still open.

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

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

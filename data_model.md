# PulseAI — Data Model (Phase 2)

Star schema for the enriched feedback data, implemented in `backend/models.py` and
loaded by `backend/pipeline/model.py`. Renders as a diagram directly on GitHub, or
in any Mermaid-aware Markdown viewer.

```mermaid
erDiagram
    DIM_SOURCE ||--o{ FACT_FEEDBACK : "one source has many feedback items"
    DIM_FEEDBACK_TYPE ||--o{ FACT_FEEDBACK : "one type has many feedback items"
    FACT_FEEDBACK ||--o{ FACT_FEEDBACK_CATEGORY : "one feedback item, many category links"
    DIM_CATEGORY ||--o{ FACT_FEEDBACK_CATEGORY : "one category, many feedback links"

    DIM_SOURCE {
        int id PK
        string name
    }

    DIM_FEEDBACK_TYPE {
        int id PK
        string name
    }

    DIM_CATEGORY {
        int id PK
        string name
        string severity
    }

    FACT_FEEDBACK {
        int id PK
        int source_id FK
        int feedback_type_id FK
        string sentiment
        text feedback_text
        timestamptz timestamp
    }

    FACT_FEEDBACK_CATEGORY {
        int feedback_id "PK, FK"
        int category_id "PK, FK"
    }
```

## Reading the diagram

- **`fact_feedback`** is the fact table — grain is one row per feedback item, same `id` as `feedback_enriched.json`.
- **`dim_source`** / **`dim_feedback_type`** — plain reference tables, linked to `fact_feedback` with a normal one-to-many foreign key (`||--o{`), since every feedback item has exactly one source and one feedback type.
- **`dim_category`** is *not* linked to `fact_feedback` directly — `category` is multi-label, so a single FK column can't represent it. Instead it connects through **`fact_feedback_category`**, the bridge table: notice both its columns are marked `PK, FK` — the *combination* of the two is the primary key, which is what allows one feedback item to link to several categories without duplicating any `fact_feedback` row.
- `severity` lives on `dim_category` as a hardcoded business-impact rating (Critical/High/Medium/Low/Unclassified) — never computed from the data, never touched by the LLM.

Full reasoning behind these choices (why a bridge table, why severity is hardcoded, why there's no `dim_date`) is in `NOTES.md`.

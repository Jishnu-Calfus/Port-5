"""
The single source of truth for "what does the data agent know exists."

Both the SQL safety gateway (sql_gateway.py) and the agent's own instructions
(agent.py) need to know exactly which tables/columns/values are real. This
file builds that list by reading it live from the actual SQLAlchemy models
and enums -- never by retyping a copy of the schema by hand -- so if the
schema ever changes, both consumers pick up the change automatically instead
of silently going stale.
"""
import backend.models  # noqa: F401 -- importing this registers every model
                        # class (FactFeedback, DimCategory, ...) onto Base's
                        # metadata below. Without this import, Base.metadata
                        # would be empty, even though the classes exist.
from backend.db import Base
from backend.models import SEVERITY_MAP
from backend.schemas import FeedbackType, Sentiment, Source, Topic

# {table_name: {column_name, ...}}
# Built straight from Base.metadata, which SQLAlchemy already maintains for
# every model class -- this can never drift from the real schema.
ALLOWED_TABLES: dict[str, set[str]] = {
    table_name: {column.name for column in table.columns}
    for table_name, table in Base.metadata.tables.items()
}

# {enum_name: {valid_string_value, ...}}
# One entry per thing an LLM-drafted WHERE clause might compare a column
# against. Values come straight from the real enums/map, not retyped.
ALLOWED_ENUM_LITERALS: dict[str, set[str]] = {
    "sentiment": {member.value for member in Sentiment},
    "source": {member.value for member in Source},
    "feedback_type": {member.value for member in FeedbackType},
    "category": {member.value for member in Topic},
    "severity": set(SEVERITY_MAP.values()),
}

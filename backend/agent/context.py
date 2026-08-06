"""
The object carried through one agent run. This never reaches the model --
the OpenAI Agents SDK threads it through in-process only, which makes it
the right place to hold a live database session.
"""
from dataclasses import dataclass

from sqlalchemy.orm import Session


@dataclass
class AgentContext:
    session: Session  # a backend.db.ROSessionLocal() session, read-only role
    last_validated_sql: str | None = None  # set by the guardrail in tools.py,
                                            # read by run_sql's own body, so the
                                            # query that actually executes is
                                            # exactly the one that was checked

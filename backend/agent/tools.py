"""
The one tool the data agent has: run_sql. Its input guardrail is where the
actual SQL safety check happens (sql_gateway.py) -- the tool's own body
trusts its input completely, because nothing reaches it without already
having passed validate_and_rewrite().
"""
import json
from typing import Any

from agents import RunContextWrapper, function_tool
from agents.tool_guardrails import ToolGuardrailFunctionOutput, ToolInputGuardrailData, tool_input_guardrail
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.agent.context import AgentContext
from backend.agent.sql_gateway import SQLValidationError, validate_and_rewrite


class SqlResult(BaseModel):
    """What run_sql returns. The model sees this as its tool result; later,
    run_agent_query() also reads it back out of the run's history to feed
    chart_selector.py -- the same object serves both purposes."""
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    error: str | None = None


@tool_input_guardrail
def validate_sql_guardrail(data: ToolInputGuardrailData) -> ToolGuardrailFunctionOutput:
    """Runs before run_sql's body ever executes. This is the actual safety
    boundary for this feature -- everything else is defense-in-depth around
    it (the read-only database role, the row limit)."""
    try:
        arguments = json.loads(data.context.tool_arguments)
        raw_sql = arguments["sql"]
    except (json.JSONDecodeError, KeyError):
        return ToolGuardrailFunctionOutput.reject_content(
            "Malformed tool call -- resend a JSON object with a single 'sql' field."
        )

    try:
        safe_sql = validate_and_rewrite(raw_sql)
    except SQLValidationError as exc:
        # reject_content, not raise_exception: the model sees this message
        # as if it were the tool's own result and can draft corrected SQL
        # in the same run. raise_exception would abort the whole run on the
        # first bad draft, which is too aggressive for an expected,
        # self-correctable mistake.
        return ToolGuardrailFunctionOutput.reject_content(
            f"SQL rejected: {exc.reason} Rewrite the query to fix this and call run_sql again."
        )

    # Stash the exact validated (and possibly LIMIT-rewritten) SQL so the
    # tool body below executes precisely what was checked -- never the
    # model's original, unvalidated text.
    data.context.context.last_validated_sql = safe_sql
    return ToolGuardrailFunctionOutput.allow()


def execute_sql(session, sql: str) -> SqlResult:
    """The actual execution logic, kept separate from the @function_tool
    wrapper below so it can be unit-tested directly against a real
    database session, without needing to construct the SDK's internal
    ToolContext machinery by hand."""
    try:
        result = session.execute(text(sql))
        columns = list(result.keys())
        rows = [dict(zip(columns, row)) for row in result.fetchall()]
        return SqlResult(sql=sql, columns=columns, rows=rows, row_count=len(rows))
    except SQLAlchemyError as exc:
        # A query that passed the safety gateway can still fail at the
        # database (a real type error, an unsupported cast, etc.) -- that's
        # a correctness problem, not a security one, so it's reported back
        # to the model the same way a rejected query is, not raised.
        session.rollback()  # required: a failed statement leaves this
                             # session's transaction unusable for any later
                             # retry in the same run otherwise
        return SqlResult(
            sql=sql, columns=[], rows=[], row_count=0,
            error=f"The database rejected this query: {exc}. Rewrite it and try again.",
        )


@function_tool(tool_input_guardrails=[validate_sql_guardrail])
def run_sql(wrapper: RunContextWrapper[AgentContext], sql: str) -> SqlResult:
    """Run a single read-only SELECT against the feedback database and
    return the matching rows. `sql` must reference only the tables and
    columns described in your instructions."""
    context = wrapper.context
    safe_sql = context.last_validated_sql or sql
    return execute_sql(context.session, safe_sql)

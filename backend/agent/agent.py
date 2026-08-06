"""
The data agent itself: an OpenAI Agents SDK Agent with one tool (run_sql),
plus the orchestration function that runs it and turns the result into the
API's public response shape.

Two things are deliberately never trusted to the agent, even though it
could be asked to guess at both: which SQL is safe to run (that's
sql_gateway.py, enforced by tools.py's guardrail, before anything reaches
Postgres) and which chart best displays the result (that's
chart_selector.py, run here, after the agent has already finished, using
the real columns that came back). The agent's only real job is two things
language models are actually good at: drafting SQL syntax, and writing a
short, grounded explanation of numbers it's already seen.
"""
from agents import Agent, MaxTurnsExceeded, ModelSettings, Runner
from agents.items import ToolCallOutputItem
from pydantic import BaseModel, Field

from backend.agent.chart_selector import select_chart
from backend.agent.context import AgentContext
from backend.agent.schema_registry import ALLOWED_ENUM_LITERALS, ALLOWED_TABLES
from backend.agent.tools import SqlResult, run_sql
from backend.config import AGENT_MAX_TURNS, AGENT_MODEL
from backend.db import ROSessionLocal
from backend.schemas import AgentAnswer


class AgentFinalOutput(BaseModel):
    """The only thing trusted directly from the model's final answer. The
    executed SQL, result columns/rows, and chart type are all derived
    separately in run_agent_query() from the tool call the agent actually
    made -- never restated here, because a model re-typing something it
    already produced is exactly where it can quietly drift from what
    really ran."""
    narrative: str = Field(
        ...,
        description="2-4 plain-prose sentences explaining the result, grounded only in the run_sql output actually returned.",
    )


class AgentQueryFailed(Exception):
    """Raised when the agent never produced a valid, executed query --
    fail closed, never a fabricated answer."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _render_schema_block() -> str:
    lines = ["TABLES AND COLUMNS (exact names, case-sensitive):"]
    for table, columns in sorted(ALLOWED_TABLES.items()):
        lines.append(f"- {table}({', '.join(sorted(columns))})")
    lines.append("")
    lines.append("VALID LITERAL VALUES (copy these exactly, including case):")
    for name, values in sorted(ALLOWED_ENUM_LITERALS.items()):
        lines.append(f"- {name}: {', '.join(sorted(values))}")
    return "\n".join(lines)


INSTRUCTIONS = f"""You are a read-only data analyst for a consumer-fintech feedback warehouse.

{_render_schema_block()}

Rules:
- category is MULTI-LABEL: never join dim_category directly to fact_feedback. Always go
  fact_feedback -> fact_feedback_category -> dim_category. source and feedback_type are
  single-valued: use fact_feedback.source_id / fact_feedback.feedback_type_id directly.
- Time windows like "last quarter" or "this month" are relative to MAX(fact_feedback.timestamp)
  in the data, never wall-clock today -- this is a batch dataset that can lag real time.
- Write exactly one SELECT statement. No other statement types, no multiple statements.
- Always call run_sql before answering a question that needs data -- never answer from memory.
  If run_sql's guardrail rejects your SQL, read the reason and correct the query; don't resend
  the same SQL unchanged.
- After run_sql returns rows, write a short, plain-prose narrative grounded only in those rows.
  Never invent a number. If zero rows came back, say so plainly rather than guessing why.

Boundary cases:
- "Compare fee complaints by source" needs the 3-way join above (fact_feedback_category filtered
  to category = 'Fees & Pricing', joined to dim_category and to dim_source) -- fact_feedback
  joined only to dim_source would silently include every category, not just fee complaints.
- "How has churn risk trended monthly" filters dim_feedback_type.name = 'churn_risk' via
  fact_feedback.feedback_type_id, grouped by month -- not sentiment = 'negative', which is a
  different, unrelated dimension.
"""

agent = Agent(
    name="DataAgent",
    instructions=INSTRUCTIONS,
    tools=[run_sql],
    output_type=AgentFinalOutput,
    model=AGENT_MODEL,
    # temperature=0 for the same reason every Ollama call elsewhere in this
    # repo uses temperature=0: drafting correct SQL is a precision task,
    # not a creative one -- letting the model sample randomly here is what
    # produced meaningfully different (and sometimes invalid) SQL for the
    # same question across repeated calls during testing.
    model_settings=ModelSettings(temperature=0),
)


def _last_successful_sql_result(new_items) -> SqlResult | None:
    """Walks the run's history for the last run_sql call that actually
    returned rows without error -- never the model's own restatement of
    what it queried. If an earlier draft was rejected or errored and a
    later one succeeded, the model's narrative is grounded in that later
    result, so that's the one chart_selector.py should see too."""
    last_result = None
    for item in new_items:
        if not isinstance(item, ToolCallOutputItem):
            continue
        output = item.output
        try:
            if isinstance(output, SqlResult):
                result = output
            elif isinstance(output, dict):
                result = SqlResult.model_validate(output)
            else:
                result = SqlResult.model_validate_json(output)
        except Exception:
            continue
        if result.error is None:
            last_result = result
    return last_result


async def run_agent_query(question: str) -> AgentAnswer:
    """Runs one full data-agent turn: draft SQL -> validate -> execute ->
    narrate -> (separately) pick a chart. This is the only function other
    code (the FastAPI route) should call."""
    session = ROSessionLocal()
    context = AgentContext(session=session)
    try:
        try:
            result = await Runner.run(agent, question, context=context, max_turns=AGENT_MAX_TURNS)
        except MaxTurnsExceeded:
            raise AgentQueryFailed(
                "Could not produce a safe, valid query for this question after several attempts. "
                "Try rephrasing it more specifically."
            )

        sql_result = _last_successful_sql_result(result.new_items)
        if sql_result is None:
            raise AgentQueryFailed(
                "The agent did not run a validated query, so no grounded answer is available."
            )

        chart_type, chart_data = select_chart(sql_result.columns, sql_result.rows)
        final: AgentFinalOutput = result.final_output

        return AgentAnswer(
            answer=final.narrative,
            sql=sql_result.sql,
            chart_type=chart_type,
            chart_data=chart_data,
            row_count=sql_result.row_count,
        )
    finally:
        session.close()

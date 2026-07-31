"""
Weekly narrative summary: the LLM narrates from numbers aggregations.py and
priority.py have already computed -- it never re-derives or invents numbers
itself, same "sandwich" principle as the rest of the project.

Simplification worth calling out: this demo dataset spans ~2.5 weeks total,
not a live, continuously-growing feed. Rather than carve out an arbitrary
"last 7 days" slice that would (a) drop most of the small dataset and (b) show
different totals than the KPI/priority panels sitting right above it on the
same dashboard, the summary narrates the same full dataset those panels show
-- consistent numbers everywhere, no separate windowing logic to maintain.
"""
from sqlalchemy.orm import Session

from aggregations import kpi_summary
from llm_client import generate_structured
from priority import compute_priority
from schemas import WeeklySummary

SYSTEM_PROMPT_SUMMARY = """You write a short, 3-4 sentence weekly summary of user feedback for a \
product/CX team, using ONLY the numbers provided below. Never invent a number, category, or example \
that isn't given to you. Be specific and actionable -- name the categories that need attention, not \
just "some categories had issues."."""


def generate_weekly_summary(session: Session) -> WeeklySummary:
    kpis = kpi_summary(session)
    top_priority = compute_priority(session, top_n=3)

    stats_lines = [
        f"Total feedback: {kpis['total_feedback']}",
        f"Negative sentiment: {kpis['negative_pct']}%",
        f"Most active category: {kpis['top_category']}",
        f"Categories with critical severity and active negative feedback: {kpis['critical_open_issues']}",
        "Top priority actions (severity x volume x share-negative):",
    ]
    for row in top_priority:
        stats_lines.append(
            f"- {row['category']} (severity={row['severity']}, volume={row['volume']}, "
            f"negative share={row['share_negative']:.0%}, score={row['score']})"
        )

    user_prompt = "\n".join(stats_lines)
    return generate_structured(SYSTEM_PROMPT_SUMMARY, user_prompt, WeeklySummary)

from pydantic import BaseModel, Field
from enum import Enum
from typing import List


class Topic(str, Enum):
    account_access   = "Account Access & Freezes"
    transfers        = "Transfers & Payments"
    fraud_security   = "Fraud & Security"
    disputes         = "Disputes & Refunds"
    verification     = "Identity Verification / KYC"
    funding          = "Funding & Linking"
    fees             = "Fees & Pricing"
    support          = "Customer Support"
    performance      = "App Performance & Reliability"
    usability        = "Usability & UX"
    feature_request  = "Feature Requests"
    other            = "Other / Uncategorised"


class Sentiment(str, Enum):
    positive = "positive"; neutral = "neutral"; negative = "negative"


class Source(str, Enum):
    Survey = "Survey"; Tickets = "Tickets"; Reviews = "Reviews"


class FeedbackType(str, Enum):
    bug="bug"; complaint="complaint"; feature_request="feature_request"
    question="question"; churn_risk="churn_risk"; praise="praise"


class StagingRecord(BaseModel):
    """Normalized record before LLM enrichment (output of the ETL step)."""
    id: int = Field(..., description="Unique identifier for the feedback record")
    source: Source = Field(..., description="Source the feedback came from")
    feedback: str = Field(..., description="Raw feedback text")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


class Classification(BaseModel):
    """The only fields the LLM is asked to produce."""
    category: List[Topic] = Field(..., min_length=1, description="Multi-label taxonomy categories")
    feedback_type: FeedbackType = Field(..., description="Type of feedback provided")
    sentiment: Sentiment = Field(..., description="Sentiment analysis result")


class EnrichedData(Classification):
    """Final enriched record: staging fields + LLM classification, merged in code."""
    id: int = Field(..., description="Unique identifier for the enriched data")
    timestamp: str = Field(..., description="Timestamp when the data was enriched")
    source: Source = Field(..., description="Source associated with the enriched data")
    feedback: str = Field(..., description="Feedback given by the user")

class RAGSynthesis(BaseModel):
    """What the LLM actually produces -- cites excerpts by their 1-based
    position in the numbered list it was given, never by reproducing a date
    string itself, since that's a formatting task small models get wrong."""
    answer: str = Field(..., description="Synthesized answer, grounded only in the provided weekly excerpts. If the question is about a pattern, trend, or recurrence, name the specific week(s) it shows up in directly in this text.")
    cited_excerpts: List[int] = Field(..., description="1-based position (in the numbered list of weekly excerpts provided) of every excerpt the answer draws on")


class RAGAnswer(BaseModel):
    """Public shape returned by the API/frontend -- citations resolved to real
    week_start dates in code, not trusted from LLM-formatted text."""
    answer: str = Field(..., description="Synthesized answer, grounded only in the provided weekly excerpts")
    cited_weeks: List[str] = Field(..., description="week_start date (YYYY-MM-DD) of every weekly excerpt the answer draws on")


class WeeklySummary(BaseModel):
    summary: str = Field(..., description="Narrative summary grounded only in the provided computed numbers")


class WeeklyRAGSummary(BaseModel):
    """The only LLM-authored piece of a weekly RAG document -- everything else
    (stats, deltas, quotes) is rendered deterministically in code."""
    headline: str = Field(..., description="One-sentence takeaway for the week, grounded only in the numbers provided")
    narrative: str = Field(..., description="2-3 sentence analysis, grounded only in the numbers provided")


class AgentAnswer(BaseModel):
    """Public response shape for POST /api/agent/ask. sql/chart_type/chart_data
    are all derived deterministically in backend/agent/agent.py, never trusted
    as free-form model output -- see AgentFinalOutput in agent.py for the one
    thing that IS taken directly from the model (the narrative)."""
    answer: str = Field(..., description="Plain-prose explanation of the result, grounded only in the executed query's rows")
    sql: str = Field(..., description="The exact SQL that was validated and executed")
    chart_type: str | None = Field(None, description="One of bar/diverging_bar/donut/line/stat/grouped_bar, or null if there's nothing chartable")
    chart_data: dict | list | None = Field(None, description="Reshaped to match the chosen chart component's expected props (grouped_bar: a list of {label, data} entries, one bar chart per entry)")
    row_count: int = Field(..., description="Number of rows the executed query returned")
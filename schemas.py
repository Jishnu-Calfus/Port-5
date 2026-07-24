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

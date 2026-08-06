"""
Phase 2 data model: a star schema for the enriched feedback data.
Dimensions: source, feedback_type, category. category is multi-label, so it's
linked via a bridge table (fact_feedback_category) rather than a plain FK column —
same reasoning as before: a feedback item can have more than one category, but
source and feedback_type are always exactly one value per item.
"""
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db import Base
from backend.schemas import Sentiment, Topic

# Static severity per category — a business judgment call, not derived from
# the data, so it's hardcoded here rather than asked of the LLM or computed.
SEVERITY_MAP: dict[str, str] = {
    Topic.account_access.value:  "Critical",
    Topic.transfers.value:       "Critical",
    Topic.fraud_security.value:  "Critical",
    Topic.disputes.value:        "High",
    Topic.verification.value:    "High",
    Topic.funding.value:         "High",
    Topic.fees.value:            "High",
    Topic.support.value:         "High",
    Topic.performance.value:     "Medium",
    Topic.usability.value:       "Low",
    Topic.feature_request.value: "Low",
    Topic.other.value:           "Unclassified",
}


class DimSource(Base):
    __tablename__ = "dim_source"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)


class DimFeedbackType(Base):
    __tablename__ = "dim_feedback_type"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)


class DimCategory(Base):
    __tablename__ = "dim_category"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)


class FactFeedback(Base):
    __tablename__ = "fact_feedback"

    id: Mapped[int] = mapped_column(primary_key=True)  # reuses feedback_enriched.id
    source_id: Mapped[int] = mapped_column(ForeignKey("dim_source.id"), nullable=False)
    feedback_type_id: Mapped[int] = mapped_column(ForeignKey("dim_feedback_type.id"), nullable=False)
    sentiment: Mapped[Sentiment] = mapped_column(
        Enum(Sentiment, name="sentiment_enum", native_enum=True), nullable=False
    )
    feedback_text: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    source: Mapped["DimSource"] = relationship()
    feedback_type: Mapped["DimFeedbackType"] = relationship()
    categories: Mapped[list["DimCategory"]] = relationship(secondary="fact_feedback_category")


class FactFeedbackCategory(Base):
    """Bridge table: one row per (feedback, category) pair."""
    __tablename__ = "fact_feedback_category"

    feedback_id: Mapped[int] = mapped_column(ForeignKey("fact_feedback.id"), primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("dim_category.id"), primary_key=True)

"""
Phase 3: FastAPI layer wrapping the existing aggregation/priority/summary/RAG
logic as JSON endpoints. Routes are thin -- each one calls a function that
already exists and returns its result; no service/repository layers.
"""
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.analytics import aggregations, priority, summary, weekly_aggregations
from backend.rag import rag
from backend.db import SessionLocal
from backend.schemas import RAGAnswer, WeeklySummary

app = FastAPI(title="PulseAI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

#DB session access dependency for FastAPI endpoints
def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@app.get("/api/kpis")
def get_kpis(session: Session = Depends(get_session)):
    return aggregations.kpi_summary(session)


@app.get("/api/priority")
def get_priority(session: Session = Depends(get_session)):
    return priority.compute_priority(session, top_n=4)


@app.get("/api/categories")
def get_categories(session: Session = Depends(get_session)):
    return aggregations.category_volume(session)


@app.get("/api/sentiment")
def get_sentiment(session: Session = Depends(get_session)):
    return aggregations.sentiment_by_category(session)


@app.get("/api/sources")
def get_sources(session: Session = Depends(get_session)):
    return aggregations.feedback_by_source(session)


@app.get("/api/trend")
def get_trend(session: Session = Depends(get_session)):
    return aggregations.volume_trend(session)


@app.get("/api/current-week")
def get_current_week(session: Session = Depends(get_session)):
    return weekly_aggregations.compute_current_week(session)


@app.get("/api/summary", response_model=WeeklySummary)
def get_summary(session: Session = Depends(get_session)):
    return summary.generate_weekly_summary(session)

#request model for the /api/ask endpoint
class AskRequest(BaseModel):
    question: str
    top_k: int = 3


@app.post("/api/ask", response_model=RAGAnswer)
def post_ask(request: AskRequest):
    return rag.ask(request.question, top_k=request.top_k)

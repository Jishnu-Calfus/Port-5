from sqlalchemy.orm import Session
from backend.models import FactFeedback
from backend.rag.vector_store import collection

def get_feedback_records(session: Session):
    return session.query(FactFeedback).all()

def index_feedback(records: list[FactFeedback])-> None:
    #populating the vector store with the feedback records
    ids = [str(fact.id) for fact in records]
    documents = [fact.feedback_text for fact in records]
    metadatas = [
        {
            "source": fact.source.name,
            "feedback_type": fact.feedback_type.name,
            "sentiment": fact.sentiment.value,
            "categories" : ",".join([cat.name for cat in fact.categories]),
            "timestamp": fact.timestamp.isoformat(),
        }
        for fact in records
    ]

    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )
    

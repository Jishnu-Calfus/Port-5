from backend.rag.vector_store import weekly_collection
from backend.pipeline.llm_client import generate_structured
from backend.schemas import RAGAnswer, RAGSynthesis

SYSTEM_PROMPT_RAG = """You answer questions about user feedback using ONLY the numbered weekly excerpts \
provided below. Each excerpt covers one week -- category/source/sentiment statistics, a headline and \
analysis, plus a few feedback quotes inside the excerpt purely as supporting color, never as a citation \
target. Never use outside knowledge, and never state a specific number that isn't in an excerpt.

Write the answer as 2-4 plain prose sentences, as if speaking to someone -- no markdown headers, no \
bullet lists, no section titles, and never copy any excerpt's "Category breakdown" or "Headline" section \
verbatim. Read across ALL excerpts provided before answering, not just the first or most detailed one.

If the question asks about a pattern, trend, or something recurring, your job is specifically to \
compare excerpts against each other and report what's common across them -- explicitly name every \
distinct week (by its date, e.g. "the week of 2026-04-27" -- never by its bracket number like "[2]") \
where it shows up, not only one.

Populate `cited_excerpts` with the number of every excerpt your answer actually draws on (e.g. excerpt \
"[2]" -> the integer 2). Never put a feedback item id there -- it holds excerpt numbers only.

If the excerpts don't contain enough information to answer, say so plainly, and name which week(s) or \
categories a follow-up database query could look into for more exact detail."""

def retrieve(query: str, top_k: int = 3):
    results = weekly_collection.query(
        query_texts=[query],
        n_results=top_k
    )
    return results

def synthesize(question: str, retrieved_excerpts: list[dict]) -> RAGAnswer:
    week_ids = retrieved_excerpts['ids'][0]
    documents = retrieved_excerpts['documents'][0]

    excerpts = "\n\n".join(
        f'[{i}] "{doc}"' for i, doc in enumerate(documents, start=1)
    )
    user_prompt = f"Question: {question}\n\nWeekly excerpts:\n{excerpts}"

    synthesis = generate_structured(SYSTEM_PROMPT_RAG, user_prompt, RAGSynthesis)
    cited_weeks = [week_ids[i - 1] for i in synthesis.cited_excerpts if 1 <= i <= len(week_ids)]
    return RAGAnswer(answer=synthesis.answer, cited_weeks=cited_weeks)

def ask(question: str, top_k: int = 3) -> RAGAnswer:
    retrieved = retrieve(question, top_k)
    return synthesize(question , retrieved)
from vector_store import collection
from llm_client import generate_structured
from schemas import RAGAnswer

SYSTEM_PROMPT_RAG = """You answer questions about user feedback using ONLY the excerpts provided below. \
Never use outside knowledge.

You must populate the `cited_ids` field with the id of every single feedback excerpt that supports \
your answer — mentioning an id in your answer text is NOT enough on its own, it must also appear in \
`cited_ids`. If your answer draws on any excerpt at all, `cited_ids` must not be empty.

If the excerpts don't contain enough information to answer, say so plainly in your answer, and only \
then is it correct for `cited_ids` to be empty."""

def retrieve(query: str, top_k: int = 5):
    results = collection.query(
        query_texts=[query],
        n_results=top_k
    )
    return results

def synthesize(question: str, retrieved_excerpts: list[dict]) -> RAGAnswer:
    ids = retrieved_excerpts['ids'][0]
    documents = retrieved_excerpts['documents'][0]

    excerpts =  "\n\n".join(
        f'[id={fid}] "{doc}"' for fid, doc in zip(ids, documents)
    )
    user_prompt = f"Question: {question}\n\nFeedback excerpts:\n{excerpts}"

    return generate_structured(SYSTEM_PROMPT_RAG, user_prompt, RAGAnswer)

def ask(question: str, top_k: int = 5) -> RAGAnswer:
    retrieved = retrieve(question, top_k)
    return synthesize(question , retrieved)
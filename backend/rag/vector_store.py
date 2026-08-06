import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
from backend.config import OLLAMA_HOST

_embedding_function = OllamaEmbeddingFunction(
    url = OLLAMA_HOST,
    model_name = "nomic-embed-text",
)

_client = chromadb.PersistentClient(path="data/chroma") 

collection = _client.get_or_create_collection(
    name="feedback",
    embedding_function=_embedding_function
)

# One vector per ISO week (~52-54/year regardless of weekly feedback volume) --
# the RAG knowledge base, replacing per-item raw dumping into `collection` above.
weekly_collection = _client.get_or_create_collection(
    name="feedback_weekly_summaries",
    embedding_function=_embedding_function
)
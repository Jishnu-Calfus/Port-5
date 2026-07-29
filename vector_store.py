import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
from config import OLLAMA_HOST

_embedding_function = OllamaEmbeddingFunction(
    url = OLLAMA_HOST,
    model_name = "nomic-embed-text",
)

_client = chromadb.PersistentClient(path="data/chroma") 

collection = _client.get_or_create_collection(
    name="feedback",
    embedding_function=_embedding_function
)
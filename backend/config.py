#custom configs for environment variables and file path setting for redundant files

import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://pulseai:pulseai@localhost:5432/pulseai")

# Read-only database connection for the data agent (see backend/agent/). This
# points at a separate Postgres role that only has SELECT granted -- a real
# permission boundary, not just a naming convention -- so even a buggy or
# adversarial query can't write, no matter what code calls it.
DATABASE_READ_URL = os.getenv("DATABASE_READ_URL")

# The data agent is the one feature in this app that uses a paid, hosted
# model (OpenAI's Agents SDK) instead of local Ollama -- everything else
# (classification, RAG, embeddings) stays fully local/free.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AGENT_MODEL = os.getenv("AGENT_MODEL", "gpt-4.1-mini")
AGENT_MAX_TURNS = int(os.getenv("AGENT_MAX_TURNS", "8"))

DATA_DIR = "data"
RAW_DIR = f"{DATA_DIR}/raw"
STAGING_DIR = f"{DATA_DIR}/staging"
ENRICHED_DIR = f"{DATA_DIR}/enriched"

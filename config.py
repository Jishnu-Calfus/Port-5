#custom configs for environment variables and file path setting for redundant files

import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")

DATA_DIR = "data"
RAW_DIR = f"{DATA_DIR}/raw"
STAGING_DIR = f"{DATA_DIR}/staging"
ENRICHED_DIR = f"{DATA_DIR}/enriched"

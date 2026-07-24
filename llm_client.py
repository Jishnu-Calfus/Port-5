import json

import ollama
from pydantic import BaseModel, ValidationError

from config import OLLAMA_HOST, OLLAMA_MODEL

_client = ollama.Client(host=OLLAMA_HOST)

MAX_RETRIES = 2


class LLMOutputError(Exception):
    """Raised when the model fails to produce schema-valid JSON after all retries."""


def generate_structured(system_prompt: str, user_prompt: str, schema: type[BaseModel]) -> BaseModel:
    """
    Call the local Ollama model with temperature=0 and a JSON-schema-constrained
    response, then validate the result against `schema`. Retries with the
    validation error fed back to the model on failure, so a bad response can
    self-correct instead of silently corrupting the enriched dataset.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        response = _client.chat(
            model=OLLAMA_MODEL,
            messages=messages,
            format=schema.model_json_schema(),
            options={"temperature": 0},
        )
        raw = response["message"]["content"]
        try:
            return schema.model_validate_json(raw)
        except (ValidationError, json.JSONDecodeError) as exc:
            last_error = exc
            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": f"That response was invalid: {exc}. Reply again with ONLY valid JSON matching the schema.",
            })

    raise LLMOutputError(f"Model failed to produce valid {schema.__name__} after {MAX_RETRIES + 1} attempts: {last_error}")

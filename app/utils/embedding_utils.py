from __future__ import annotations

from app.config import config
from app.utils.logger import get_logger

logger = get_logger("EmbeddingUtils")


def load_genai_client():
    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError("google-genai is not installed") from exc

    return genai.Client(api_key=config.GEMINI_API_KEY)


async def get_embedding_async(text: str, client=None) -> list[float]:
    if not text or not text.strip():
        return []

    if client is None:
        client = load_genai_client()

    response = await client.aio.models.embed_content(
        model="text-embedding-004",
        contents=text.strip(),
    )

    if hasattr(response, "embeddings") and response.embeddings:
        return list(response.embeddings[0].values)
    elif hasattr(response, "embedding") and response.embedding:
        return list(response.embedding.values)

    return []

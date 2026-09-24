import httpx
from app.config import settings

VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"


async def embed_texts(texts: list[str], input_type: str = "document") -> list[list[float]]:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            VOYAGE_URL,
            headers={"Authorization": f"Bearer {settings.VOYAGE_API_KEY}"},
            json={"input": texts, "model": settings.VOYAGE_MODEL, "input_type": input_type},
            timeout=30,
        )
        resp.raise_for_status()
        return [item["embedding"] for item in resp.json()["data"]]

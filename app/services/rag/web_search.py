import httpx
from app.config import settings

TAVILY_URL = "https://api.tavily.com/search"


async def search_web(query: str, max_results: int = 3) -> list[dict]:
    """Returns [{"url", "content"}, ...] used only when KB retrieval (narrow + broad) fails."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            TAVILY_URL,
            json={
                "api_key": settings.TAVILY_API_KEY,
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        return [{"url": r["url"], "content": r["content"]} for r in data.get("results", [])]

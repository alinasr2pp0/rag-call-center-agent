from pinecone import Pinecone
from app.config import settings

_pc: Pinecone | None = None
_index = None  # lazy-initialized — see _get_index()


def _get_index():
    """
    Built on first use rather than at import time: Pinecone(api_key=...)
    raises immediately if the key is missing, which would otherwise crash
    the whole app at startup (this module is imported transitively by
    app.main) even before PINECONE_API_KEY has been filled in.
    """
    global _pc, _index
    if _index is None:
        _pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        _index = _pc.Index(settings.PINECONE_INDEX_NAME)
    return _index


def upsert_kb_article(article: dict, embeddings: list[list[float]]) -> None:
    """One vector per problem_variant, all pointing back at the same KB article."""
    vectors = [
        {
            "id": f"{article['id']}::{i}",
            "values": emb,
            "metadata": {
                "kb_article_id": article["id"],
                "variant_text": variant,
                "solution_text": article["solution_text"],
                "category": article.get("category", ""),
            },
        }
        for i, (variant, emb) in enumerate(zip(article["problem_variants"], embeddings))
    ]
    _get_index().upsert(vectors=vectors)


def query_kb(query_embedding: list[float], k: int = 5, min_score: float = 0.75) -> list[dict]:
    """
    Attempt-1 (narrow): default k=5, min_score=0.75 — only confident matches.
    Attempt-2 (broad): call with a higher k and a lower min_score for a wider net
    before falling back to web search.
    """
    result = _get_index().query(vector=query_embedding, top_k=k, include_metadata=True)
    return [
        {
            "kb_article_id": m["metadata"]["kb_article_id"],
            "text": m["metadata"]["variant_text"],
            "solution_text": m["metadata"]["solution_text"],
            "category": m["metadata"].get("category"),
            "score": m["score"],
        }
        for m in result["matches"]
        if m["score"] >= min_score
    ]


def delete_kb_article(article_id: str) -> None:
    _get_index().delete(filter={"kb_article_id": article_id})

"""
Run once to load kb_articles_sample.json into Postgres and Pinecone.
Usage: python seed_kb.py
"""
import asyncio
import json
from datetime import datetime
from app.db import async_session, init_db
from app.models import KBArticle
from app.services.rag.embeddings import embed_texts
from app.services.rag.vectorstore import upsert_kb_article


async def main():
    await init_db()
    with open("kb_articles_sample.json", encoding="utf-8") as f:
        articles = json.load(f)

    async with async_session() as db:
        for article in articles:
            db.add(KBArticle(
                id=article["id"],
                category=article["category"],
                subcategory=article.get("subcategory"),
                title=article["title"],
                problem_variants=article["problem_variants"],
                solution_text=article["solution_text"],
                solution_steps=article.get("solution_steps"),
                escalate_if=article.get("escalate_if"),
                tags=article.get("tags"),
                source=article.get("source"),
                last_verified_at=datetime.strptime(article["last_verified_at"], "%Y-%m-%d").date()
                if article.get("last_verified_at") else None,
            ))

            embeddings = await embed_texts(article["problem_variants"], input_type="document")
            upsert_kb_article(article, embeddings)
            print(f"Seeded {article['id']}")

        await db.commit()

    print(f"Done. {len(articles)} KB articles indexed.")


if __name__ == "__main__":
    asyncio.run(main())

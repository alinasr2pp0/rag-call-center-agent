import uuid
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.models import Ticket, Message, Resolution, Call, Escalation, KBArticle
from app.services.auth import require_staff, require_admin
from app.services.rag.embeddings import embed_texts
from app.services.rag.vectorstore import upsert_kb_article, delete_kb_article

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------- Tickets & escalations (any logged-in staff can view) ----------

@router.get("/tickets")
async def list_tickets(
    status: str | None = None,
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_staff),
):
    query = select(Ticket).order_by(Ticket.opened_at.desc())
    if status:
        query = query.where(Ticket.status == status)
    if category:
        query = query.where(Ticket.category == category)
    result = await db.execute(query)
    tickets = result.scalars().all()
    return [
        {
            "id": t.id, "status": t.status, "category": t.category,
            "resolution_attempts": t.resolution_attempts,
            "opened_at": t.opened_at, "closed_at": t.closed_at,
        }
        for t in tickets
    ]


@router.get("/tickets/{ticket_id}")
async def ticket_detail(ticket_id: str, db: AsyncSession = Depends(get_db), _user: dict = Depends(require_staff)):
    ticket = await db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    messages = (await db.execute(select(Message).where(Message.ticket_id == ticket_id).order_by(Message.created_at))).scalars().all()
    resolutions = (await db.execute(select(Resolution).where(Resolution.ticket_id == ticket_id).order_by(Resolution.created_at))).scalars().all()
    calls = (await db.execute(select(Call).where(Call.ticket_id == ticket_id).order_by(Call.scheduled_at))).scalars().all()
    escalations = (await db.execute(select(Escalation).where(Escalation.ticket_id == ticket_id))).scalars().all()

    return {
        "ticket": {"id": ticket.id, "status": ticket.status, "category": ticket.category,
                   "resolution_attempts": ticket.resolution_attempts, "opened_at": ticket.opened_at, "closed_at": ticket.closed_at},
        "messages": [{"sender": m.sender, "content": m.content, "created_at": m.created_at} for m in messages],
        "resolutions": [{"source": r.source, "answer_text": r.answer_text, "confidence_score": r.confidence_score} for r in resolutions],
        "calls": [{"status": c.status, "outcome": c.outcome, "transcript": c.transcript, "duration_seconds": c.duration_seconds} for c in calls],
        "escalations": [{"reason": e.reason, "escalated_at": e.escalated_at, "assigned_agent": e.assigned_agent} for e in escalations],
    }


@router.get("/escalations")
async def list_escalations(db: AsyncSession = Depends(get_db), _user: dict = Depends(require_staff)):
    result = await db.execute(select(Escalation).order_by(Escalation.escalated_at.desc()))
    return [
        {"id": e.id, "ticket_id": e.ticket_id, "reason": e.reason,
         "escalated_at": e.escalated_at, "assigned_agent": e.assigned_agent}
        for e in result.scalars().all()
    ]


@router.get("/stats")
async def dashboard_stats(db: AsyncSession = Depends(get_db), _user: dict = Depends(require_staff)):
    total = (await db.execute(select(func.count()).select_from(Ticket))).scalar_one()
    resolved = (await db.execute(select(func.count()).select_from(Ticket).where(Ticket.status == "resolved_confirmed"))).scalar_one()
    escalated = (await db.execute(select(func.count()).select_from(Ticket).where(Ticket.status == "escalated"))).scalar_one()
    open_ = (await db.execute(select(func.count()).select_from(Ticket).where(Ticket.status.in_(["open", "resolved_by_rag"])))).scalar_one()
    return {"total": total, "resolved": resolved, "escalated": escalated, "open": open_}


# ---------- KB management (write operations require admin role) ----------

class KBArticleIn(BaseModel):
    category: str
    subcategory: str | None = None
    title: str
    problem_variants: list[str]
    solution_text: str
    solution_steps: list[str] | None = None
    escalate_if: list[str] | None = None
    tags: list[str] | None = None
    source: str | None = None


@router.get("/kb")
async def list_kb(db: AsyncSession = Depends(get_db), _user: dict = Depends(require_staff)):
    result = await db.execute(select(KBArticle).order_by(KBArticle.id))
    return [
        {"id": a.id, "category": a.category, "subcategory": a.subcategory, "title": a.title,
         "problem_variants": a.problem_variants, "solution_text": a.solution_text,
         "solution_steps": a.solution_steps, "escalate_if": a.escalate_if,
         "tags": a.tags, "last_verified_at": a.last_verified_at}
        for a in result.scalars().all()
    ]


@router.post("/kb")
async def create_kb_article(body: KBArticleIn, db: AsyncSession = Depends(get_db), _user: dict = Depends(require_admin)):
    new_id = f"KB-{uuid.uuid4().hex[:6].upper()}"
    article = KBArticle(
        id=new_id, category=body.category, subcategory=body.subcategory, title=body.title,
        problem_variants=body.problem_variants, solution_text=body.solution_text,
        solution_steps=body.solution_steps, escalate_if=body.escalate_if,
        tags=body.tags, source=body.source, last_verified_at=date.today(),
    )
    db.add(article)
    await db.commit()

    embeddings = await embed_texts(body.problem_variants, input_type="document")
    upsert_kb_article({"id": new_id, "category": body.category, "problem_variants": body.problem_variants,
                        "solution_text": body.solution_text}, embeddings)

    return {"id": new_id, "ok": True}


@router.put("/kb/{article_id}")
async def update_kb_article(article_id: str, body: KBArticleIn, db: AsyncSession = Depends(get_db), _user: dict = Depends(require_admin)):
    article = await db.get(KBArticle, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="KB article not found")

    article.category = body.category
    article.subcategory = body.subcategory
    article.title = body.title
    article.problem_variants = body.problem_variants
    article.solution_text = body.solution_text
    article.solution_steps = body.solution_steps
    article.escalate_if = body.escalate_if
    article.tags = body.tags
    article.source = body.source
    article.last_verified_at = date.today()
    await db.commit()

    delete_kb_article(article_id)
    embeddings = await embed_texts(body.problem_variants, input_type="document")
    upsert_kb_article({"id": article_id, "category": body.category, "problem_variants": body.problem_variants,
                        "solution_text": body.solution_text}, embeddings)

    return {"id": article_id, "ok": True}


@router.delete("/kb/{article_id}")
async def delete_kb_article_endpoint(article_id: str, db: AsyncSession = Depends(get_db), _user: dict = Depends(require_admin)):
    article = await db.get(KBArticle, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="KB article not found")
    await db.delete(article)
    await db.commit()
    delete_kb_article(article_id)
    return {"ok": True}

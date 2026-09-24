from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.db import get_db
from app.models import Customer, Ticket, Message, Call
from app.services.agent.resolution_agent import attempt_resolution
from app.services.agent.scheduler import schedule_followup_call

router = APIRouter(prefix="/tickets", tags=["tickets"])


class NewProblemRequest(BaseModel):
    customer_phone: str
    customer_name: str | None = None
    problem_text: str


@router.post("/message")
async def submit_problem(req: NewProblemRequest, db: AsyncSession = Depends(get_db)):
    customer = Customer(phone=req.customer_phone, name=req.customer_name)
    db.add(customer)
    await db.flush()

    ticket = Ticket(customer_id=customer.id, status="open")
    db.add(ticket)
    await db.flush()

    db.add(Message(ticket_id=ticket.id, sender="customer", content=req.problem_text))

    result = await attempt_resolution(db, ticket, req.problem_text)

    db.add(Message(ticket_id=ticket.id, sender="agent", content=result.answer_text))
    ticket.status = "resolved_by_rag" if result.answer_text else "open"
    await db.commit()

    # 3-minute delayed confirmation call (confirmed business rule)
    await schedule_followup_call(ticket.id)

    return {
        "ticket_id": ticket.id,
        "answer": result.answer_text,
        "confidence": result.confidence,
        "source": result.source,
        "followup_call_in_seconds": settings.FOLLOWUP_CALL_DELAY_SECONDS,
    }


@router.get("/{ticket_id}/status")
async def get_ticket_status(ticket_id: str, db: AsyncSession = Depends(get_db)):
    """Polled by the frontend to show the confirmation-call result as soon as it lands."""
    ticket = await db.get(Ticket, ticket_id)
    if not ticket:
        return {"error": "ticket not found"}

    result = await db.execute(
        select(Call).where(Call.ticket_id == ticket_id).order_by(Call.scheduled_at.desc())
    )
    latest_call = result.scalars().first()

    return {
        "ticket_status": ticket.status,
        "resolution_attempts": ticket.resolution_attempts,
        "latest_call": {
            "status": latest_call.status,
            "outcome": latest_call.outcome,
            "started_at": latest_call.started_at,
            "ended_at": latest_call.ended_at,
        } if latest_call else None,
    }

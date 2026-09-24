from datetime import datetime
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.db import get_db
from app.models import Call, Ticket, Message, Escalation
from app.services.agent import telephony
from app.services.rag import llm
from app.services.agent.resolution_agent import attempt_resolution
from app.services.agent.scheduler import schedule_retry_call

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

GREETING = "معك المساعد الآلي للمتابعة. هل تم حل المشكلة اللي كانت عندك؟"
ASK_DESCRIBE_AGAIN = "تمام، ممكن توصفلي المشكلة تاني بالتفصيل عشان أقدر أساعدك أكتر؟"
CLOSING_RESOLVED = "تمام جدًا، سعيد إن المشكلة اتحلت. شكرًا لوقتك ويومك سعيد."
TRANSFERRING = "حسنًا، هحولك دلوقتي لأحد ممثلي خدمة العملاء للمساعدة."

# Vonage call-status values that mean the call never really connected.
UNREACHABLE_STATUSES = {"busy", "failed", "rejected", "unanswered", "timeout", "cancelled"}


@router.get("/answer/{call_id}")
async def answer_endpoint(call_id: str):
    """Vonage fetches this NCCO the moment the call is answered."""
    return telephony.build_gather_ncco(call_id, GREETING)


@router.post("/event/{call_id}")
async def event_callback(call_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Vonage posts call-status events here as JSON with a "status" field:
    started|ringing|answered|completed|busy|failed|rejected|unanswered|timeout|cancelled.
    On an unreachable status, retry up to MAX_CALL_RETRIES times before escalating.
    """
    body = await request.json()
    call_status = body.get("status", "")

    call = await db.get(Call, call_id)
    if not call:
        return {"ok": True}

    if call_status == "answered" and not call.started_at:
        call.started_at = datetime.utcnow()

    if call_status in UNREACHABLE_STATUSES:
        call.status = "failed"
        call.outcome = call_status
        await db.commit()
        await _handle_unreachable(db, call)
        return {"ok": True}

    if call_status == "completed":
        call.ended_at = datetime.utcnow()
        if call.started_at:
            call.duration_seconds = int((call.ended_at - call.started_at).total_seconds())
        if call.status not in ("resolved_confirmed", "transferred", "escalated"):
            call.status = "completed"

    await db.commit()
    return {"ok": True}


async def _handle_unreachable(db: AsyncSession, call: Call) -> None:
    ticket = await db.get(Ticket, call.ticket_id)
    if not ticket:
        return

    if call.retry_count >= settings.MAX_CALL_RETRIES:
        ticket.status = "escalated"
        db.add(Escalation(ticket_id=ticket.id, call_id=call.id, reason="call_unreachable"))
        await db.commit()
        return

    await schedule_retry_call(ticket.id, call.retry_count + 1)


@router.post("/gather/{call_id}")
async def gather_endpoint(call_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Vonage posts the recognized speech here (the eventUrl named inside our
    "input" NCCO action) as JSON: {"speech": {"results": [{"text": "...", ...}]}, ...}.
    Mirrors the confirm -> retry -> escalate loop, driven by request/response
    NCCO turns.
    """
    body = await request.json()
    speech_results = body.get("speech", {}).get("results", [])
    customer_text = (speech_results[0].get("text", "") if speech_results else "").strip()

    call = await db.get(Call, call_id)
    ticket = await db.get(Ticket, call.ticket_id) if call else None
    if not call or not ticket:
        return telephony.build_say_hangup_ncco("حدث خطأ، من فضلك حاول لاحقًا.")

    if not call.started_at:
        call.started_at = datetime.utcnow()

    if not customer_text:
        await db.commit()
        prompt = ASK_DESCRIBE_AGAIN if call.dialog_state == "awaiting_problem_description" else GREETING
        return telephony.build_gather_ncco(call_id, prompt)

    db.add(Message(ticket_id=ticket.id, sender="customer", content=customer_text))

    if call.dialog_state == "awaiting_problem_description":
        result = await attempt_resolution(db, ticket, customer_text)

        if result.should_escalate or not result.answer_text:
            return await _escalate(db, call, ticket, reason="max_attempts_reached")

        db.add(Message(ticket_id=ticket.id, sender="agent", content=result.answer_text))
        call.dialog_state = "awaiting_confirmation"
        await db.commit()
        reply = f"{result.answer_text} هل الكلام ده بيحل المشكلة؟"
        return telephony.build_gather_ncco(call_id, reply)

    # dialog_state == "awaiting_confirmation": did the ORIGINAL solution resolve it?
    classification = await llm.classify_call_response(customer_text)

    if classification == "resolved":
        ticket.status = "resolved_confirmed"
        ticket.closed_at = datetime.utcnow()
        call.outcome = "resolved_confirmed"
        call.dialog_state = "done"
        await db.commit()
        return telephony.build_say_hangup_ncco(CLOSING_RESOLVED)

    if ticket.resolution_attempts >= settings.MAX_RESOLUTION_ATTEMPTS:
        return await _escalate(db, call, ticket, reason="max_attempts_reached")

    call.dialog_state = "awaiting_problem_description"
    await db.commit()
    return telephony.build_gather_ncco(call_id, ASK_DESCRIBE_AGAIN)


async def _escalate(db: AsyncSession, call: Call, ticket: Ticket, reason: str) -> list[dict]:
    """Returns an NCCO that speaks a short message then live-connects the
    call to the human agent line (see telephony.build_transfer_ncco)."""
    ticket.status = "escalated"
    call.outcome = "transferred_to_agent"
    call.dialog_state = "done"
    db.add(Escalation(ticket_id=ticket.id, call_id=call.id, reason=reason))
    await db.commit()
    return telephony.build_transfer_ncco(TRANSFERRING)

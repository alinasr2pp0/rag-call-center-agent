"""
Scheduling is DB-backed, not in-memory: schedule_* only writes a Call row
with status='scheduled' and a scheduled_at timestamp. A background poller
(run_call_dispatcher, started once in app/main.py's startup hook) checks
Postgres every CALL_DISPATCH_POLL_SECONDS for due calls and places them.

This means a scheduled confirmation/retry call survives a process restart —
the intent lives in the database, not in an asyncio.sleep() that dies with
the process. No extra infra (Celery/Redis) required.
"""
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select
from app.config import settings
from app.db import async_session
from app.models import Call, Customer, Ticket
from app.services.agent.telephony import place_outbound_call


async def schedule_followup_call(ticket_id: str) -> None:
    async with async_session() as db:
        db.add(Call(
            ticket_id=ticket_id,
            call_type="confirmation",
            status="scheduled",
            scheduled_at=datetime.utcnow() + timedelta(seconds=settings.FOLLOWUP_CALL_DELAY_SECONDS),
        ))
        await db.commit()


async def schedule_retry_call(ticket_id: str, retry_count: int) -> None:
    async with async_session() as db:
        db.add(Call(
            ticket_id=ticket_id,
            call_type="confirmation",
            status="scheduled",
            retry_count=retry_count,
            scheduled_at=datetime.utcnow() + timedelta(seconds=settings.CALL_RETRY_DELAY_SECONDS),
        ))
        await db.commit()


async def run_call_dispatcher() -> None:
    """Long-running background loop — started once via asyncio.create_task at startup."""
    while True:
        await asyncio.sleep(settings.CALL_DISPATCH_POLL_SECONDS)
        try:
            await _dispatch_due_calls()
        except Exception as e:  # noqa: BLE001 - never let one bad row kill the dispatcher
            print(f"[call_dispatcher] error: {e}")


async def _dispatch_due_calls() -> None:
    async with async_session() as db:
        result = await db.execute(
            select(Call).where(Call.status == "scheduled", Call.scheduled_at <= datetime.utcnow())
        )
        due_calls = result.scalars().all()

        for call in due_calls:
            ticket = await db.get(Ticket, call.ticket_id)
            customer = await db.get(Customer, ticket.customer_id) if ticket else None

            if not customer:
                call.status = "failed"
                continue

            call.provider_call_id = place_outbound_call(customer.phone, call.id)
            call.status = "in_progress"

        if due_calls:
            await db.commit()

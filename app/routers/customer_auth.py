from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.models import Customer, Ticket
from app.services.agent import verify
from app.services.auth import create_access_token, require_customer

router = APIRouter(prefix="/customer-auth", tags=["customer-auth"])


class RequestOtpBody(BaseModel):
    phone: str


class VerifyOtpBody(BaseModel):
    phone: str
    request_id: str
    code: str


@router.post("/request-otp")
async def request_otp(body: RequestOtpBody):
    """Sends a one-time code by SMS. No account needed beforehand — a phone
    number is enough to identify a returning customer."""
    request_id = verify.start_verification(body.phone)
    return {"request_id": request_id}


@router.post("/verify-otp")
async def verify_otp(body: VerifyOtpBody, db: AsyncSession = Depends(get_db)):
    """Checks the code; on success, issues a customer-scoped JWT tied to
    their phone number so /my/tickets only ever returns their own data."""
    if not verify.check_verification(body.request_id, body.code):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="كود غير صحيح أو منتهي")

    token = create_access_token(subject_id=body.phone, role="customer", phone=body.phone)
    return {"access_token": token, "role": "customer"}


@router.get("/my/tickets")
async def my_tickets(db: AsyncSession = Depends(get_db), user: dict = Depends(require_customer)):
    """A customer's own ticket history — filtered by the phone number in their verified token."""
    phone = user.get("phone")
    result = await db.execute(select(Customer).where(Customer.phone == phone))
    customers = result.scalars().all()
    customer_ids = [c.id for c in customers]
    if not customer_ids:
        return []

    result = await db.execute(
        select(Ticket).where(Ticket.customer_id.in_(customer_ids)).order_by(Ticket.opened_at.desc())
    )
    return [
        {"id": t.id, "status": t.status, "category": t.category, "opened_at": t.opened_at, "closed_at": t.closed_at}
        for t in result.scalars().all()
    ]

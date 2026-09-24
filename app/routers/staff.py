from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.models import StaffUser
from app.services.auth import hash_password, require_superadmin, STAFF_ROLES

router = APIRouter(prefix="/staff", tags=["staff"])


class CreateStaffBody(BaseModel):
    username: str
    password: str
    role: str  # "agent" | "admin" | "superadmin"


class UpdateRoleBody(BaseModel):
    role: str


@router.get("")
async def list_staff(db: AsyncSession = Depends(get_db), _user: dict = Depends(require_superadmin)):
    result = await db.execute(select(StaffUser).order_by(StaffUser.username))
    return [{"id": s.id, "username": s.username, "role": s.role, "created_at": s.created_at} for s in result.scalars().all()]


@router.post("")
async def create_staff(body: CreateStaffBody, db: AsyncSession = Depends(get_db), _user: dict = Depends(require_superadmin)):
    if body.role not in STAFF_ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {STAFF_ROLES}")

    existing = await db.execute(select(StaffUser).where(StaffUser.username == body.username))
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail="اسم المستخدم مستخدم بالفعل")

    staff = StaffUser(username=body.username, password_hash=hash_password(body.password), role=body.role)
    db.add(staff)
    await db.commit()
    return {"id": staff.id, "username": staff.username, "role": staff.role}


@router.put("/{staff_id}/role")
async def update_staff_role(staff_id: str, body: UpdateRoleBody, db: AsyncSession = Depends(get_db), _user: dict = Depends(require_superadmin)):
    if body.role not in STAFF_ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {STAFF_ROLES}")

    staff = await db.get(StaffUser, staff_id)
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")

    staff.role = body.role
    await db.commit()
    return {"id": staff.id, "role": staff.role}


@router.delete("/{staff_id}")
async def delete_staff(staff_id: str, db: AsyncSession = Depends(get_db), _user: dict = Depends(require_superadmin)):
    staff = await db.get(StaffUser, staff_id)
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    if staff.id == _user.get("sub"):
        raise HTTPException(status_code=400, detail="لا يمكنك حذف حسابك الخاص")

    await db.delete(staff)
    await db.commit()
    return {"ok": True}

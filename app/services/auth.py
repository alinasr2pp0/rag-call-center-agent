from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# Role hierarchy: superadmin > admin > agent (staff roles), plus a separate
# "customer" role for the phone-verified customer portal (see verify.py).
STAFF_ROLES = ("superadmin", "admin", "agent")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(subject_id: str, role: str, **extra_claims) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": subject_id, "role": role, "exp": expire, **extra_claims}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


async def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    return decode_token(creds.credentials)


def require_staff(user: dict = Depends(get_current_user)) -> dict:
    """Any logged-in staff member (superadmin, admin, or agent) — not a customer token."""
    if user.get("role") not in STAFF_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff role required")
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Admin or superadmin — KB writes, etc."""
    if user.get("role") not in ("admin", "superadmin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user


def require_superadmin(user: dict = Depends(get_current_user)) -> dict:
    """Superadmin only — managing staff accounts themselves."""
    if user.get("role") != "superadmin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superadmin role required")
    return user


def require_customer(user: dict = Depends(get_current_user)) -> dict:
    """A phone-verified customer token (see verify.py) — scoped to their own data only."""
    if user.get("role") != "customer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Customer login required")
    return user

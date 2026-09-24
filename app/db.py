from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.config import settings
from app.models import Base, StaffUser

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _ensure_default_superadmin()


async def _ensure_default_superadmin():
    """Bootstraps the very first account as superadmin — the top of the
    staff hierarchy — so there's always someone able to create further
    admin/agent accounts via /staff."""
    from app.services.auth import hash_password  # local import to avoid circular import
    async with async_session() as db:
        result = await db.execute(select(StaffUser).where(StaffUser.role == "superadmin"))
        if result.scalars().first():
            return
        db.add(StaffUser(
            username=settings.ADMIN_DEFAULT_USERNAME,
            password_hash=hash_password(settings.ADMIN_DEFAULT_PASSWORD),
            role="superadmin",
        ))
        await db.commit()


async def get_db():
    async with async_session() as session:
        yield session

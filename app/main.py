import asyncio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.db import init_db
from app.routers import chat, webhooks, auth, admin, customer_auth, staff
from app.services.agent.scheduler import run_call_dispatcher

app = FastAPI(title="RAG Call Center Agent (Arabic)")

_origins = ["*"] if settings.ALLOWED_ORIGINS.strip() == "*" else [
    o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(webhooks.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(customer_auth.router)
app.include_router(staff.router)


@app.on_event("startup")
async def on_startup():
    _check_production_secrets()
    await init_db()
    asyncio.create_task(run_call_dispatcher())


def _check_production_secrets() -> None:
    """Refuse to start in production with placeholder secrets left in .env."""
    if settings.ENVIRONMENT != "production":
        return
    if settings.JWT_SECRET == "271ff08622e8a4a4164706a83f07bddafeb60884b0521dc66ad7e232713045d1":
        raise RuntimeError("ENVIRONMENT=production but JWT_SECRET is still the local-dev default — generate a new secret (e.g. `python -c \"import secrets; print(secrets.token_hex(32))\"`) and set it in .env")
    if settings.ADMIN_DEFAULT_PASSWORD == "changeme123":
        raise RuntimeError("ENVIRONMENT=production but ADMIN_DEFAULT_PASSWORD is still the placeholder default — set a real password in .env")


@app.get("/health")
async def health():
    return {"status": "ok"}


# Mounted last and deliberately: Starlette matches routes in registration
# order, and a mount at "/" matches every path. Any @app.get(...) added
# after this line would silently 404 behind the static file server instead
# of reaching your endpoint.
app.mount("/", StaticFiles(directory="static", html=True), name="static")

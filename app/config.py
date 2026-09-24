from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Embeddings (Voyage AI) ---
    VOYAGE_API_KEY: str = ""
    VOYAGE_MODEL: str = "voyage-3"

    # --- Vector DB (Pinecone) ---
    PINECONE_API_KEY: str = ""
    PINECONE_INDEX_NAME: str = "call-center-kb"
    PINECONE_ENVIRONMENT: str = ""

    # --- LLM (OpenRouter, fallback chain) ---
    OPENROUTER_API_KEY: str = ""
    LLM_MODEL_PRIMARY: str = "openai/gpt-4o"
    LLM_MODEL_FALLBACKS: list[str] = ["meta-llama/llama-3.1-70b-instruct", "mistralai/mixtral-8x7b"]

    # --- Web search fallback (Tavily) ---
    TAVILY_API_KEY: str = ""

    # --- Telephony (Vonage Voice API) ---
    # Voice API auth is JWT-based via an Application (not simple key/secret):
    # create one at dashboard.nexmo.com > Applications, enable Voice, and
    # download its private key.
    VONAGE_APPLICATION_ID: str = ""
    VONAGE_PRIVATE_KEY: str = ""          # full PEM key content (see .env.example for how to load it)
    VONAGE_FROM_NUMBER: str = ""          # your Vonage virtual number, digits only, no "+"
    PUBLIC_BASE_URL: str = ""
    HUMAN_AGENT_TRANSFER_NUMBER: str = "" # digits only, no "+"

    # --- Database ---
    # Defaults to SQLite (zero install, just a local file) - fine for local
    # dev/testing. Swap for a real Postgres URL before production, since
    # SQLite doesn't handle concurrent writes from multiple simultaneous
    # requests well: postgresql+asyncpg://user:pass@localhost:5432/call_center_rag
    DATABASE_URL: str = "sqlite+aiosqlite:///./call_center_rag.db"

    # --- Staff auth (Admin dashboard + KB management) ---
    JWT_SECRET: str = "271ff08622e8a4a4164706a83f07bddafeb60884b0521dc66ad7e232713045d1"
    JWT_EXPIRE_MINUTES: int = 480
    ADMIN_DEFAULT_USERNAME: str = "admin"
    ADMIN_DEFAULT_PASSWORD: str = "changeme123"  # change immediately after first login

    # --- Business rules (confirmed by Ali) ---
    FOLLOWUP_CALL_DELAY_SECONDS: int = 180   # 3 minutes
    MAX_RESOLUTION_ATTEMPTS: int = 3

    # --- Call retry (no-answer/busy/failed) ---
    MAX_CALL_RETRIES: int = 2
    CALL_RETRY_DELAY_SECONDS: int = 60
    CALL_DISPATCH_POLL_SECONDS: int = 10

    # --- CORS ---
    ALLOWED_ORIGINS: str = "*"  # comma-separated list in production, e.g. "https://your-frontend.com"

    # --- Deployment safety ---
    ENVIRONMENT: str = "development"  # set to "production" to enable the startup secret check

    class Config:
        env_file = ".env"


settings = Settings()

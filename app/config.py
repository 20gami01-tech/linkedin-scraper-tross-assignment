import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Note: LinkedIn credentials are NOT configured here. This server
    # accepts them per-request via headers (see app/main.py) so the
    # deployment itself never stores a LinkedIn account's credentials.
    API_KEY: str | None = os.getenv("API_KEY") or None
    CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "3600"))
    PORT: int = int(os.getenv("PORT", "8000"))


settings = Settings()

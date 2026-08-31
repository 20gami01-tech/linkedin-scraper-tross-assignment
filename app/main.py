import hashlib
import time

from fastapi import FastAPI, HTTPException, Header, Depends

from .config import settings
from .models import ProfileRequest, ProfileResponse
from .utils import extract_public_identifier, now_iso
from .linkedin_client import get_client, LinkedInAuthError, LinkedInEndpointError
from .parser import parse_profile

app = FastAPI(
    title="LinkedIn Profile API",
    description="Accepts a LinkedIn profile URL and returns structured profile data as JSON.",
    version="1.0.0",
)

# Simple in-memory TTL cache: {"<caller>:<public_identifier>": (fetched_at, payload)}.
# Scoped per-caller (not just per-profile) because different callers supply
# different LinkedIn sessions and may not have the same visibility into a
# given profile. Good enough for a single-instance deployment; swap for
# Redis if you scale to multiple workers/instances.
_cache: dict[str, tuple[float, dict]] = {}


def _check_api_key(x_api_key: str | None = Header(default=None)):
    """Protects this hosted API itself — separate from the LinkedIn
    credentials below, which authenticate the *scrape*, not the caller."""
    if settings.API_KEY and x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key header.")


def _get_linkedin_credentials(
    x_linkedin_cookie: str | None = Header(default=None, alias="X-LinkedIn-Cookie"),
    x_linkedin_email: str | None = Header(default=None, alias="X-LinkedIn-Email"),
    x_linkedin_password: str | None = Header(default=None, alias="X-LinkedIn-Password"),
):
    """
    Each request supplies its own LinkedIn session — the server holds no
    LinkedIn account credentials in its own config. Provide EITHER:
      - X-LinkedIn-Cookie: a valid 'li_at' cookie value (recommended), or
      - X-LinkedIn-Email + X-LinkedIn-Password: scripted login (best-effort;
        LinkedIn often throws a CAPTCHA/2FA checkpoint at this).
    """
    if not x_linkedin_cookie and not (x_linkedin_email and x_linkedin_password):
        raise HTTPException(
            status_code=400,
            detail=(
                "Missing LinkedIn credentials. Provide the 'X-LinkedIn-Cookie' "
                "header (recommended), or both 'X-LinkedIn-Email' and "
                "'X-LinkedIn-Password' headers."
            ),
        )
    return {
        "li_at": x_linkedin_cookie,
        "email": x_linkedin_email,
        "password": x_linkedin_password,
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post(
    "/api/v1/profile",
    response_model=ProfileResponse,
    dependencies=[Depends(_check_api_key)],
)
def get_profile(body: ProfileRequest, li_creds: dict = Depends(_get_linkedin_credentials)):
    try:
        public_id = extract_public_identifier(body.linkedin_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    caller_key = hashlib.sha256(
        (li_creds["li_at"] or li_creds["email"] or "").encode("utf-8")
    ).hexdigest()[:16]
    cache_key = f"{caller_key}:{public_id}"

    cached = _cache.get(cache_key)
    if cached and (time.time() - cached[0] < settings.CACHE_TTL_SECONDS):
        return cached[1]

    client = get_client(
        li_at=li_creds["li_at"], email=li_creds["email"], password=li_creds["password"]
    )
    try:
        raw = client.get_raw_profile(public_id)
    except LinkedInAuthError as e:
        raise HTTPException(status_code=502, detail=f"LinkedIn authentication failed: {e}")
    except LinkedInEndpointError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:  # noqa: BLE001 — surface anything unexpected as a 502
        raise HTTPException(status_code=502, detail=f"Unexpected error contacting LinkedIn: {e}")

    parsed = parse_profile(raw, public_id, body.linkedin_url)
    parsed["scraped_at"] = now_iso()

    _cache[cache_key] = (time.time(), parsed)
    return parsed

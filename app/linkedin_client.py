"""
Thin client for LinkedIn's internal 'Voyager' API — the JSON API the
linkedin.com front end itself calls. It is not publicly documented, so the
endpoint paths and payload shapes below were derived by reverse engineering
(via browser network tab and cross-referencing prior open-source efforts).
LinkedIn can and does change these without notice.

Auth is per-request, not server-side config: the caller supplies their own
LinkedIn session (a cookie, or email/password) as HTTP headers on each API
call (see app/main.py). This server never stores a LinkedIn account's
credentials at rest — only a short-lived, in-memory session cache keyed by
the supplied credential, so repeated calls from the same caller don't
re-authenticate every time.
"""

import time
import hashlib

import httpx

VOYAGER_BASE = "https://www.linkedin.com/voyager/api"
LOGIN_PAGE_URL = "https://www.linkedin.com/login"
LOGIN_SUBMIT_URL = "https://www.linkedin.com/checkpoint/lg/login-submit"

# LinkedIn retired the old `identity/profiles/{id}/profileView` endpoint
# (it now returns 410 Gone). Profile data currently lives behind the
# "dash" endpoint below. `decorationId` is itself versioned by LinkedIn
# (the trailing "-93") and gets bumped periodically — if this starts
# returning 410/400 again, open a LinkedIn profile in a browser, check the
# Network tab for a request to `dash/profiles`, and copy the current
# decorationId value from its query string into this constant.
DASH_PROFILE_DECORATION_ID = (
    "com.linkedin.voyager.dash.deco.identity.profile.FullProfileWithEntities-93"
)

DEFAULT_HEADERS = {
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "x-li-lang": "en_US",
    "x-restli-protocol-version": "2.0.0",
    "accept": "application/vnd.linkedin.normalized+json+2.1",
}

# How long an authenticated session is kept in memory before being
# re-authenticated. Purely a perf optimization (avoids hitting LinkedIn's
# login page on every single API call) — it is not a guarantee that the
# underlying LinkedIn session is still valid; a 401 mid-window still
# triggers a fresh re-auth (see get_raw_profile below).
SESSION_CACHE_TTL_SECONDS = 30 * 60


class LinkedInAuthError(Exception):
    """Raised when authentication with LinkedIn fails or hits a checkpoint."""


class LinkedInEndpointError(Exception):
    """Raised when LinkedIn rejects the request shape itself (410/400) —
    almost always a sign the endpoint or decorationId version has moved on,
    not a transient problem worth retrying as-is."""


class LinkedInClient:
    """
    Wraps one LinkedIn-authenticated session. Construct it with either:

    - `li_at`: a valid `li_at` cookie value copied from an already
      authenticated browser session (recommended — sidesteps LinkedIn's
      automated-login checkpoint entirely), or
    - `email` + `password`: the client performs the login POST itself.
      LinkedIn frequently flags scripted logins with a CAPTCHA/2FA
      checkpoint that can't be solved headlessly, so treat this as
      best-effort / fallback.
    """

    def __init__(
        self,
        li_at: str | None = None,
        email: str | None = None,
        password: str | None = None,
    ):
        self._li_at = li_at
        self._email = email
        self._password = password
        self._client = httpx.Client(
            headers=DEFAULT_HEADERS, timeout=20, follow_redirects=True
        )
        self._authenticated = False

    def authenticate(self) -> None:
        if self._li_at:
            self._authenticate_with_cookie(self._li_at)
        elif self._email and self._password:
            self._authenticate_with_credentials(self._email, self._password)
        else:
            raise LinkedInAuthError(
                "No LinkedIn credentials supplied. Provide the "
                "'X-LinkedIn-Cookie' header (recommended), or both "
                "'X-LinkedIn-Email' and 'X-LinkedIn-Password' headers."
            )
        self._authenticated = True

    def _authenticate_with_cookie(self, li_at: str) -> None:
        # Visiting the login page first seeds a JSESSIONID, which LinkedIn
        # also expects echoed back as the csrf-token header on API calls.
        self._client.get(LOGIN_PAGE_URL)
        jsessionid = self._client.cookies.get("JSESSIONID", "")
        self._client.cookies.set("li_at", li_at, domain=".linkedin.com")
        self._client.headers["csrf-token"] = jsessionid.strip('"')

    def _authenticate_with_credentials(self, email: str, password: str) -> None:
        self._client.get(LOGIN_PAGE_URL)
        jsessionid = self._client.cookies.get("JSESSIONID", "")
        csrf = jsessionid.strip('"')

        payload = {
            "session_key": email,
            "session_password": password,
            "JSESSIONID": jsessionid,
        }
        resp = self._client.post(
            LOGIN_SUBMIT_URL, data=payload, headers={"csrf-token": csrf}
        )

        if "checkpoint" in str(resp.url) or resp.status_code >= 400:
            raise LinkedInAuthError(
                "LinkedIn returned a security checkpoint (CAPTCHA/2FA) instead "
                "of logging in. Log in manually in a browser, copy the 'li_at' "
                "cookie value, and send it via the 'X-LinkedIn-Cookie' header "
                "instead of email/password."
            )
        if "li_at" not in self._client.cookies:
            raise LinkedInAuthError("Login did not return a valid session cookie.")

        self._client.headers["csrf-token"] = csrf

    def get_raw_profile(self, public_identifier: str) -> dict:
        if not self._authenticated:
            self.authenticate()

        url = (
            f"{VOYAGER_BASE}/identity/dash/profiles"
            f"?q=memberIdentity&memberIdentity={public_identifier}"
            f"&decorationId={DASH_PROFILE_DECORATION_ID}"
        )
        resp = self._client.get(url)

        if resp.status_code == 401:
            # Session likely expired mid-run — re-auth once and retry.
            self._authenticated = False
            self.authenticate()
            resp = self._client.get(url)

        if resp.status_code == 404:
            raise ValueError(
                f"Profile '{public_identifier}' was not found, or is not "
                "visible with the current account (private/out-of-network)."
            )
        if resp.status_code in (429, 999):
            raise RuntimeError(
                "Rate limited or flagged by LinkedIn. Slow down request "
                "frequency and try again later."
            )
        if resp.status_code in (410, 400):
            raise LinkedInEndpointError(
                "LinkedIn rejected the request (410/400) — this usually means "
                "the decorationId version in linkedin_client.py is stale. "
                "Capture a fresh 'dash/profiles' request from your browser's "
                "Network tab and update DASH_PROFILE_DECORATION_ID."
            )

        resp.raise_for_status()
        return resp.json()


# In-memory session cache: {cache_key: (created_at, LinkedInClient)}.
# Keyed by a hash of the supplied credential so different callers (or the
# same caller across requests) reuse a session instead of re-authenticating
# with LinkedIn on every call. Never persisted to disk.
_session_cache: dict[str, tuple[float, LinkedInClient]] = {}


def _cache_key(li_at: str | None, email: str | None) -> str:
    raw = li_at or email or ""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_client(
    li_at: str | None = None,
    email: str | None = None,
    password: str | None = None,
) -> LinkedInClient:
    key = _cache_key(li_at, email)
    now = time.time()
    cached = _session_cache.get(key)
    if cached and (now - cached[0] < SESSION_CACHE_TTL_SECONDS):
        return cached[1]

    client = LinkedInClient(li_at=li_at, email=email, password=password)
    _session_cache[key] = (now, client)
    return client

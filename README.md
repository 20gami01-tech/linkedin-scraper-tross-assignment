# LinkedIn Profile API

A hosted HTTP API that accepts a LinkedIn profile URL and returns the
information on that profile — name, headline, location, about, experience,
education, skills, certifications, languages, and images — as structured
JSON.

It works by authenticating as a real LinkedIn account and calling the same
internal ("Voyager") JSON API that linkedin.com's own front end uses, rather
than screen-scraping rendered HTML.

> **Legal / ethical note:** Automated access to LinkedIn via anything other
> than their official Partner APIs is against LinkedIn's User Agreement, and
> using an account this way risks that account being restricted or banned.
> This project is intended as a technical demonstration. Don't use it to
> harvest data at scale, and be mindful of data-protection law (e.g. GDPR)
> if you store or process other people's personal data with it.
> 
> 

# Quickstart

Full details (deployment, all endpoints, limitations) are in `README.md`.
This is just the fastest path to a working local API.

## 1. Install

```bash
git clone <your-fork-url>
cd linkedin-profile-api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```


## 2. Run

```bash
uvicorn app.main:app --reload --port 8000
```

Leave this running. The API is now live at `http://localhost:8000`.

## 3. Get a LinkedIn cookie

1. Log in to linkedin.com in your browser.
2. Open DevTools → Application (Chrome) or Storage (Firefox) → Cookies →
   `https://www.linkedin.com`.
3. Copy the value of the `li_at` cookie.

## 4. Call the API

```bash
curl -X POST http://localhost:8000/api/v1/profile \
  -H "Content-Type: application/json" \
  -H "X-LinkedIn-Cookie: <the li_at value you copied>" \
  -d '{"linkedin_url": "https://www.linkedin.com/in/some-username/"}'
```

You should get back JSON with the profile's name, headline, experience,
education, skills, and more.

## Troubleshooting

- **`400 Missing LinkedIn credentials`** — you forgot the
  `X-LinkedIn-Cookie` header.
- **`401`** — your `X-API-Key` header doesn't match `API_KEY` in `.env`.
- **`404`** — the profile URL is wrong, private, or not visible to your
  LinkedIn account.
- **`429`** — you're being rate-limited by LinkedIn; wait and retry.
- **`502`** — either your `li_at` cookie has expired (get a fresh one), or
  LinkedIn changed something on their end (see "Known limitations" in
  `README.md`).


## Features

- `POST` a LinkedIn profile URL, get back structured JSON.
- Extracts: name, headline, location, industry, about/summary, profile
  photo, background image, work experience, education, skills,
  certifications, and languages.
- **No server-side LinkedIn credentials**: each caller supplies their own
  LinkedIn session via request headers (see "Auth" below). The server
  never stores a LinkedIn account's credentials at rest — only a
  short-lived, in-memory session cache to avoid re-authenticating with
  LinkedIn on every call.
- API-key protected (`X-API-Key` header) so the public deployment isn't open
  to anyone.
- In-memory response caching to avoid re-scraping the same profile too
  often (configurable TTL).
- Ships as a single Docker image — deployable to any container host.

## Approach

LinkedIn's profile pages are hydrated client-side from a private REST-ish
API under `/voyager/api/...` ("Voyager"). The approach here:

1. **Authenticate** as a LinkedIn account, using credentials the *caller*
   supplies per request (see "Auth" below) — either:
   - reusing a browser session's `li_at` cookie (recommended), or
   - performing the login POST programmatically with an email/password.
2. **Resolve** the `/in/<public-identifier>` slug from the submitted URL.
3. **Call** `GET /voyager/api/identity/dash/profiles?q=memberIdentity&memberIdentity={id}&decorationId=...`,
   which returns a normalized JSON graph: a root object plus a flat
   `included` array of typed entities (positions, education, skills,
   certifications, languages, and one or more profile-shaped objects).
   LinkedIn retired the older `identity/profiles/{id}/profileView`
   endpoint (it now returns `410 Gone`) in favor of this "dash" endpoint.
4. **Identify** the profile actually being requested: the `included` array
   can contain other profile-shaped entities (e.g. mini-profiles of
   connections), so the parser matches on `entityUrn` containing
   `fsd_profile:` rather than trusting `$type` alone.
5. **Parse**: bucket the remaining `included` entities by their `$type`
   suffix and reshape them into the flat response schema below (see
   `app/parser.py`).
6. **Serve** it all behind a small FastAPI app (see `app/main.py`), with
   caching and API-key auth.

This is the same general technique used by several well-known open-source
LinkedIn scraping libraries — it is not a novel exploit, just consumption of
an unofficial, unversioned, undocumented API that can change at any time.

## Project structure

```
app/
  main.py             FastAPI app & routes
  linkedin_client.py  Auth + Voyager API calls
  parser.py           Raw Voyager JSON -> our response schema
  models.py           Pydantic request/response models
  utils.py            URL parsing, image URL building, date formatting
  config.py           Env var loading
tests/
  test_parser.py
  test_api.py
Dockerfile
render.yaml           Optional one-click Render.com blueprint
.env.example
```

## Setup

### 1. Clone and install

```bash
git clone <your-fork-url>
cd linkedin-profile-api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure the server

Copy `.env.example` to `.env`:

```bash
cp ..env.example ..env
```

Set `API_KEY` to a secret of your choosing — clients must send it back as
an `X-API-Key` header. There's nothing LinkedIn-related to configure here:
LinkedIn credentials are supplied per-request by callers (see "Auth"
below), not stored in server config.

### 3. Run locally

```bash
uvicorn app.main:app --reload --port 8000
```

### 4. Run tests

```bash
pytest -q
```

## Auth

Two layers of auth, easy to mix up:

- **`X-API-Key`** — authenticates the *caller* to this hosted API. Set once
  by whoever runs the server (`API_KEY` in `.env`).
- **LinkedIn session headers** — authenticate the *scrape itself* to
  LinkedIn, on every request. Supply **one** of:
  - `X-LinkedIn-Cookie: <li_at value>` — **recommended.** Copy the `li_at`
    cookie from an already logged-in browser session (DevTools →
    Application → Cookies → linkedin.com → `li_at`). Sidesteps LinkedIn's
    automated-login checkpoint (CAPTCHA/2FA) entirely.
  - `X-LinkedIn-Email` + `X-LinkedIn-Password` — the server performs the
    login itself. Best-effort: LinkedIn frequently throws a checkpoint at
    scripted logins, in which case you'll get a clear 502 telling you to
    switch to cookie mode.

Sessions built from these headers are cached in memory (keyed by a hash of
the credential, TTL 30 min) so repeated calls from the same caller don't
re-authenticate with LinkedIn every time — nothing is written to disk.

## API documentation

### `POST /api/v1/profile`

**Headers**

| Header               | Required | Description                                                        |
|----------------------|----------|----------------------------------------------------------------------|
| `X-API-Key`          | Yes*     | Must match the server's `API_KEY` (*unless `API_KEY` is left unset). |
| `X-LinkedIn-Cookie`  | Yes**    | A valid `li_at` cookie value. Recommended auth mode.               |
| `X-LinkedIn-Email`   | Yes**    | Alternative to the cookie — used with the password below.          |
| `X-LinkedIn-Password`| Yes**    | Paired with `X-LinkedIn-Email`.                                     |
| `Content-Type`       | Yes      | `application/json`                                                  |

\*\* Provide either `X-LinkedIn-Cookie` alone, or both `X-LinkedIn-Email` and
`X-LinkedIn-Password`.

**Body**

```json
{ "linkedin_url": "https://www.linkedin.com/in/some-username/" }
```

**Response `200 OK`**

```json
{
  "input_url": "https://www.linkedin.com/in/some-username/",
  "public_identifier": "some-username",
  "name": { "first": "Jane", "last": "Doe", "full": "Jane Doe" },
  "headline": "Software Engineer at Acme Corp",
  "location": "Bengaluru, Karnataka, India",
  "industry": "Software Development",
  "about": "I build things...",
  "profile_picture_url": "https://media.licdn.com/dms/image/...",
  "background_image_url": "https://media.licdn.com/dms/image/...",
  "experience": [
    {
      "title": "Software Engineer",
      "company": "Acme Corp",
      "location": "Bengaluru",
      "start_date": "2024-08",
      "end_date": null,
      "description": "Backend infrastructure work."
    }
  ],
  "education": [
    {
      "school": "State University",
      "degree": "B.Tech",
      "field_of_study": "Computer Science",
      "start_date": "2018",
      "end_date": "2022"
    }
  ],
  "skills": ["Python", "Kubernetes"],
  "certifications": [
    { "name": "AWS Certified Developer", "issuing_organization": "AWS", "issue_date": "2023" }
  ],
  "languages": [{ "name": "English", "proficiency": "Native" }],
  "scraped_at": "2026-08-30T12:00:00Z"
}
```

**Error responses**

| Status | Meaning                                                        |
|--------|-----------------------------------------------------------------|
| 400    | Bad request — invalid LinkedIn URL, or missing LinkedIn auth headers. |
| 401    | Missing/incorrect `X-API-Key`.                                  |
| 404    | Profile not found, private, or not visible to the calling account. |
| 429    | LinkedIn rate-limited or flagged the request; back off.        |
| 502    | LinkedIn authentication failed, or an unexpected upstream error occurred. |

**Example**

```bash
curl -X POST https://your-deployment.example.com/api/v1/profile \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -H "X-LinkedIn-Cookie: your_li_at_cookie_value" \
  -d '{"linkedin_url": "https://www.linkedin.com/in/some-username/"}'
```

### `GET /health`

Liveness check, returns `{"status": "ok"}`. No API key required.

## Deployment

Any container host works. Three quick options:

**Render** — push this repo to GitHub, then "New +" → "Blueprint", pointing
at the repo (it will pick up `render.yaml`). Set `API_KEY` in the dashboard
— it's the only secret the server itself needs; LinkedIn credentials are
supplied per-request by callers, never configured on the host.

**Railway / Fly.io** — `railway up` or `fly launch` from the repo root; both
detect the `Dockerfile` automatically. Set the same env vars via their
secrets UI/CLI.

**Any VPS with Docker**

```bash
docker build -t linkedin-profile-api .
docker run -d -p 8000:8000 --.env-file ..env linkedin-profile-api
```

Put it behind a reverse proxy (Caddy/Nginx + Let's Encrypt, or your host's
built-in TLS termination) to serve it over HTTPS.

## Known limitations

- **Unofficial API**: Voyager is undocumented and can change field names,
  paths, or response shapes without notice, breaking the parser. This
  already happened once during development of this project — the older
  `profileView` endpoint was retired in favor of the `dash/profiles`
  endpoint used here.
- **`decorationId` drift**: the `dash/profiles` endpoint takes a
  `decorationId` query param that is itself versioned (see the trailing
  `-93` in `DASH_PROFILE_DECORATION_ID`). LinkedIn bumps this periodically;
  a `410`/`400` response after this API has worked before usually means the
  version needs updating. Fix: open a profile in a browser while logged in,
  find the `dash/profiles` request in DevTools → Network, and copy the
  current `decorationId` value into `app/linkedin_client.py`.
- **Checkpoints**: LinkedIn's anti-automation system can interrupt scripted
  logins with a CAPTCHA or "verify it's you" step that this client cannot
  solve headlessly — use the cookie-auth mode to avoid triggering it.
- **Visibility limits**: how much of a profile is visible depends on the
  scraping account's connection degree to the target and that person's own
  privacy settings — some sections may come back empty even though they're
  visible in a browser.
- **Rate limiting / account risk**: aggressive request volume from one
  account risks temporary restriction or a permanent ban; the built-in
  cache reduces but doesn't eliminate this risk.
- **Best-effort field mapping**: `app/parser.py` maps the entity types we
  observed; some profiles (e.g. with unusual sections, multiple current
  positions, or company pages instead of people) may not map perfectly.
- **No CAPTCHA/2FA solving**. `li_at` cookies eventually expire and need
  refreshing by the caller; the in-memory session cache (30 min TTL) is a
  performance optimization, not a guarantee the underlying session is
  still valid.

## License

MIT — see your own fork; add a `LICENSE` file if your submission requires one.
# linkedin-scraper-tross-assignment
# linkedin-scraper-tross-assignment
# linkedin-scraper-tross-assignment
# linkedin
# linkedin
# linkedin
# linkedin
# linkedin
# linkedin
# linkedin
# linkedin
# linkedin
# linkedin
# linkedin
# linkedin
# linkedin-scraper-tross-assignment

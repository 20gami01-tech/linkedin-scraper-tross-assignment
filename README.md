# LinkedIn Profile API

A hosted HTTP API that accepts a LinkedIn profile URL and returns the information on that profile — name, headline, location, about, experience, education, skills, certifications, languages, and images — as structured JSON.

## Quick Start — Hosted API

The API is already deployed. You do not need to clone the repository or run anything locally to use it.

### 1. Get your `li_at` cookie

The API authenticates with LinkedIn using your existing logged-in browser session.

1. Open LinkedIn and log in.
2. Open your browser's Developer Tools.
3. Go to:
   - **Chrome:** Application → Storage → Cookies → `https://www.linkedin.com`
   - **Firefox:** Storage → Cookies → `https://www.linkedin.com`
4. Find the cookie named `li_at`.
5. Copy its Value.

> **Important:** Treat your `li_at` cookie like a password. Anyone who has it may be able to use your LinkedIn session. Do not commit it to GitHub, put it in source code, or share it publicly.

### 2. Hit the hosted endpoint

Replace `<the li_at value you copied>` with your cookie value:

```bash
curl --location 'https://linkedin-scraper-tross-assignment.onrender.com/api/v1/profile' \
  --header 'X-LinkedIn-Cookie: <the li_at value you copied>' \
  --header 'Content-Type: application/json' \
  --data '{"linkedin_url": "https://www.linkedin.com/in/gupta-amish/"}'
```

The API returns the LinkedIn profile as structured JSON:

```json
{
  "input_url": "https://www.linkedin.com/in/gupta-amish/",
  "public_identifier": "gupta-amish",
  "name": {
    "first": "Amish",
    "last": "Gupta",
    "full": "Amish Gupta"
  },
  "headline": "Software Engineer",
  "location": "Bengaluru, Karnataka, India",
  "about": "...",
  "experience": [],
  "education": [],
  "skills": [],
  "certifications": [],
  "languages": []
}
```

That's it — the API is hosted and ready to use.

---

## What It Does

This API accepts a LinkedIn profile URL and returns structured profile data, including:

- Name
- Headline
- Location
- Industry
- About / summary
- Profile photo
- Background image
- Work experience
- Education
- Skills
- Certifications
- Languages

The API is protected by LinkedIn session authentication. Each request supplies the caller's own `li_at` cookie; the server does not require a server-side LinkedIn account.

## Approach

LinkedIn's profile pages are hydrated client-side from a private REST-ish API under `/voyager/api/...` ("Voyager"). This project consumes that internal API rather than scraping rendered HTML.

The process is:

1. Authenticate using the caller's existing LinkedIn browser session via the `li_at` cookie.
2. Resolve the `/in/<public-identifier>` slug from the submitted URL.
3. Call LinkedIn's `dash/profiles` Voyager endpoint.
4. Parse the normalized JSON graph returned by LinkedIn.
5. Identify the requested profile from the included entities.
6. Extract and reshape profile information into a clean JSON response.
7. Serve the result through FastAPI.

The relevant implementation is split across:

```
app/
  main.py             FastAPI app & routes
  linkedin_client.py  LinkedIn authentication & Voyager API calls
  parser.py           Raw Voyager JSON → response schema
  models.py           Pydantic request/response models
  utils.py            URL parsing, image URL building, date formatting
  config.py           Environment configuration
tests/
  test_parser.py
  test_api.py
```

## API Documentation

### `POST /api/v1/profile`

Hosted endpoint:

```
https://linkedin-scraper-tross-assignment.onrender.com/api/v1/profile
```

#### Headers

| Header | Required | Description |
|---|---|---|
| `X-LinkedIn-Cookie` | Yes | Your LinkedIn `li_at` session cookie |
| `Content-Type` | Yes | `application/json` |

#### Request

```json
{
  "linkedin_url": "https://www.linkedin.com/in/some-username/"
}
```

#### Response

```json
{
  "input_url": "https://www.linkedin.com/in/some-username/",
  "public_identifier": "some-username",
  "name": {
    "first": "Jane",
    "last": "Doe",
    "full": "Jane Doe"
  },
  "headline": "Software Engineer at Acme Corp",
  "location": "Bengaluru, Karnataka, India",
  "industry": "Software Development",
  "about": "I build things...",
  "profile_picture_url": "https://media.licdn.com/...",
  "background_image_url": "https://media.licdn.com/...",
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
  "education": [],
  "skills": [
    "Python",
    "Kubernetes"
  ],
  "certifications": [],
  "languages": [],
  "scraped_at": "2026-08-30T12:00:00Z"
}
```

### `GET /health`

The health endpoint does not require authentication:

```bash
curl https://linkedin-scraper-tross-assignment.onrender.com/health
```

Response:

```json
{
  "status": "ok"
}
```

### Error Responses

| Status | Meaning |
|---|---|
| 400 | Invalid LinkedIn URL or missing LinkedIn authentication |
| 404 | Profile not found, private, or not visible to the account |
| 429 | LinkedIn rate-limited the request |
| 502 | LinkedIn authentication failed or an upstream error occurred |

## Local Development

If you want to run the API locally instead of using the hosted deployment:

### 1. Clone and install

```bash
git clone https://github.com/20gami01-tech/linkedin-scraper-tross-assignment
cd linkedin-profile-api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure the server

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Set an `API_KEY` if you want to protect the local API:

```
API_KEY=your-secret-api-key
```

### 3. Run

```bash
uvicorn app.main:app --reload --port 8000
```

The API will be available at:

```
http://localhost:8000
```

### 4. Run tests

```bash
pytest -q
```

## Authentication

There are two authentication concepts:

### LinkedIn authentication

The API uses the caller's LinkedIn session through the `li_at` cookie:

```
X-LinkedIn-Cookie: <li_at>
```

The cookie is used to authenticate requests to LinkedIn's Voyager API.

### API authentication

When `API_KEY` is configured on the server, callers must additionally provide:

```
X-API-Key: <api-key>
```

The hosted deployment currently uses the LinkedIn cookie header for the scraping request.

## Caching

The API maintains a short-lived in-memory session cache and response cache.

This avoids unnecessarily authenticating with LinkedIn or requesting the same profile repeatedly within the configured TTL.

Nothing is written to disk.

## Deployment

The project ships as a Docker image and can be deployed to any container platform.

The repository also contains:

```
Dockerfile
render.yaml
```

The current deployment runs on Render.

## Known Limitations

### Unofficial LinkedIn API

This project uses LinkedIn's undocumented internal Voyager API rather than an official LinkedIn Partner API. LinkedIn can change these endpoints or their response formats at any time.

### decorationId drift

The `dash/profiles` endpoint requires a versioned `decorationId`. LinkedIn may periodically change this value.

If the API previously worked but starts returning 400 or 410, the `decorationId` may need to be updated in `app/linkedin_client.py`.

### LinkedIn checkpoints

Automated LinkedIn login can trigger CAPTCHA, 2FA, or other verification. Cookie authentication is therefore the recommended approach.

### Profile visibility

The amount of information returned depends on what the authenticated LinkedIn account is allowed to see and the target user's privacy settings.

### Rate limiting

Aggressive requests can trigger LinkedIn rate limits or account restrictions. The built-in caching reduces unnecessary requests but does not eliminate this risk.

### Cookie expiration

`li_at` cookies can eventually expire or become invalid. If requests begin returning authentication errors, obtain a fresh cookie from your logged-in browser session.

## Legal / Ethical Note

Automated access to LinkedIn through anything other than its official Partner APIs may violate LinkedIn's User Agreement and can put the associated account at risk of restriction or suspension.

This project is intended as a technical demonstration of interacting with an undocumented internal API. Do not use it to harvest LinkedIn data at scale, and consider applicable data-protection laws (such as GDPR) when processing or storing information about other people.

## License

MIT — see the repository for the license.

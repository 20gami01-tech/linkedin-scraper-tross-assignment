from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_missing_linkedin_credentials_returns_400():
    resp = client.post(
        "/api/v1/profile",
        json={"linkedin_url": "https://www.linkedin.com/in/someone/"},
    )
    assert resp.status_code == 400
    assert "LinkedIn" in resp.json()["detail"]


def test_invalid_url_returns_400_even_with_credentials():
    resp = client.post(
        "/api/v1/profile",
        json={"linkedin_url": "https://example.com/not-linkedin"},
        headers={"X-LinkedIn-Cookie": "fake_li_at_value"},
    )
    assert resp.status_code == 400
    assert "linkedin.com" in resp.json()["detail"]

import json
from decimal import Decimal

import pytest
from insights_support import FakeChatClient, llm_settings
from sqlalchemy import select

from app.insights.llm import TransportError
from app.metrics import default_end
from app.models import AiInsight, GscDaily
from app.routers.insights import get_chat_client, get_llm_settings

BASE = "/api/sites/arlington/insights"
DOMAIN = "arlington247lockrepair.com"
REPLY = json.dumps(
    {
        "answer_markdown": "Clicks were 12.",
        "suggested_questions": ["Which pages?", "Why mobile?"],
        "insights": [
            {
                "title": "Low CTR",
                "problem": "Few clicks",
                "evidence": [{"metric": "clicks", "value": 12, "period": "28 days"}],
                "advice": "Rewrite titles",
                "target_url": None,
                "target_kpi": "ctr",
                "priority": "high",
            }
        ],
    }
)


@pytest.fixture
def fake(client):
    fake_client = FakeChatClient([REPLY])
    client.app.dependency_overrides[get_chat_client] = lambda: fake_client
    client.app.dependency_overrides[get_llm_settings] = lambda: llm_settings()
    return fake_client


@pytest.fixture
def data(db, seeded):
    db.add(
        GscDaily(
            site=DOMAIN,
            data_date=default_end(),
            page="",
            query="",
            device="",
            country="all",
            clicks=12,
            impressions=400,
            position=Decimal("5"),
        )
    )
    db.commit()


def ask(client, question="Why are clicks low?", **extra):
    return client.post(f"{BASE}/ask", json={"question": question, **extra})


def test_status_reports_quota(client, login_as, fake):
    login_as()
    body = client.get(f"{BASE}/status").json()
    assert body == {
        "configured": True,
        "model": "primary:free",
        "used": 0,
        "budget": 45,
        "remaining": 45,
        "exhausted": False,
    }


def test_viewer_can_read_but_not_ask(client, login_as, fake, data):
    login_as()
    assert client.get(BASE).status_code == 200
    assert client.get(f"{BASE}/conversations").status_code == 200
    assert ask(client).status_code == 403
    assert fake.calls == []


def test_ask_requires_origin(client, login_as, fake, data):
    login_as("admin")
    response = client.post(
        f"{BASE}/ask", json={"question": "x"}, headers={"Origin": "https://evil.example"}
    )
    assert response.status_code == 400


def test_ask_returns_message_and_suggestions(client, login_as, fake, data):
    login_as("admin")
    response = ask(client)
    assert response.status_code == 200
    body = response.json()
    assert body["message"]["content"] == "Clicks were 12."
    assert body["message"]["suggested_questions"] == ["Which pages?", "Why mobile?"]
    assert body["insights"][0]["evidence"][0]["grounded"] is True
    conversation = client.get(f"{BASE}/conversations/{body['conversation_id']}").json()
    assert [m["role"] for m in conversation["messages"]] == ["user", "assistant"]
    listed = client.get(BASE).json()
    assert [item["title"] for item in listed] == ["Low CTR"]
    assert response.headers["cache-control"] == "no-store"


def test_ask_without_data_returns_409(client, login_as, fake, seeded):
    login_as("admin")
    response = ask(client)
    assert response.status_code == 409
    assert response.json()["detail"] == "No data stored for this website yet. Run an import first."
    assert fake.calls == []


def test_ask_rejects_blank_question(client, login_as, fake, data):
    login_as("admin")
    assert ask(client, "  \x00 ").status_code == 422


def test_quota_exhausted_returns_429(client, login_as, fake, data):
    login_as("admin")
    fake.replies = [TransportError(429, "Rate limit exceeded: free-models-per-day")]
    response = ask(client)
    assert response.status_code == 429
    assert "limit" in response.json()["detail"]


def test_not_configured_returns_503(client, login_as, fake, data):
    client.app.dependency_overrides[get_llm_settings] = lambda: llm_settings(
        openrouter_api_key=None
    )
    login_as("admin")
    assert ask(client).status_code == 503


def test_patch_status_validates_value(client, login_as, fake, data, db):
    login_as("admin")
    ask(client)
    insight_id = db.scalar(select(AiInsight.id))
    assert client.patch(f"{BASE}/{insight_id}", json={"status": "bogus"}).status_code == 422
    response = client.patch(f"{BASE}/{insight_id}", json={"status": "accepted"})
    assert response.status_code == 200 and response.json()["status"] == "accepted"
    assert client.get(BASE, params={"status": "accepted"}).json()[0]["id"] == str(insight_id)


def test_viewer_cannot_change_status(client, login_as, fake, data, db):
    login_as("admin")
    ask(client)
    insight_id = db.scalar(select(AiInsight.id))
    login_as()
    assert client.patch(f"{BASE}/{insight_id}", json={"status": "done"}).status_code == 403


def test_insights_hidden_for_unlinked_site(client, login_as, fake):
    login_as()
    response = client.get("/api/sites/site2/insights")
    assert response.status_code == 404
    assert response.json() == {"detail": "Site not found"}


def test_weekly_without_report_returns_404(client, login_as, fake, data):
    login_as("admin")
    assert client.post(f"{BASE}/weekly").status_code == 404


def test_error_never_contains_key(client, login_as, fake, data):
    login_as("admin")
    fake.replies = [TransportError(500), TransportError(500)]
    response = ask(client)
    assert response.status_code == 502
    assert "sk-" not in response.text


def test_busy_models_return_502_not_429(client, login_as, fake, data):
    login_as("admin")
    fake.replies = [TransportError(429, "rate-limited upstream")] * 2
    assert ask(client).status_code == 502
    assert client.get(f"{BASE}/status").json()["exhausted"] is False


def test_list_route_has_no_trailing_slash(client, login_as, fake):
    # Next.js strips trailing slashes before proxying; a redirect would leave the proxy.
    login_as()
    response = client.get(BASE, follow_redirects=False)
    assert response.status_code == 200

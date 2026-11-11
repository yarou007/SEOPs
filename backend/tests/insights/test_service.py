import json
from datetime import date, timedelta
from decimal import Decimal

import pytest
from insights_support import FakeChatClient, llm_settings
from sqlalchemy import func, select

from app.analysis.weekly import build_report, save_report
from app.insights.llm import LlmError
from app.insights.prompts import Evidence
from app.insights.service import ask, clean_question, generate_weekly, ground
from app.metrics import Window
from app.models import (
    AiConversation,
    AiInsight,
    AiMessage,
    GscDaily,
    Site,
    User,
    WeeklyReport,
)

DOMAIN = "arlington247lockrepair.com"
END = date(2026, 10, 28)
WINDOW = Window(END - timedelta(days=27), END)


def insight_json(value=12):
    return {
        "title": "Low CTR on home page",
        "problem": "Many impressions, few clicks",
        "evidence": [{"metric": "clicks", "value": value, "period": "current 28 days"}],
        "advice": "Rewrite the title tag",
        "target_url": "https://arlington247lockrepair.com/",
        "target_kpi": "ctr",
        "priority": "high",
    }


def chat_reply(value=12, insights=1):
    return json.dumps(
        {
            "answer_markdown": "Clicks were **12**.",
            "suggested_questions": ["Which pages lost clicks?", "What changed on mobile?"],
            "insights": [insight_json(value) for _ in range(insights)],
        }
    )


def weekly_reply():
    return json.dumps(
        {
            "summary_markdown": "## Summary\nClicks were 12.",
            "insights": [insight_json(), insight_json()],
            "suggested_questions": ["A?", "B?", "C?"],
        }
    )


@pytest.fixture
def site(db, seeded):
    db.add(
        GscDaily(
            site=DOMAIN,
            data_date=END,
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
    return db.scalar(select(Site).where(Site.domain == DOMAIN))


@pytest.fixture
def user(db, seeded):
    return db.scalar(select(User).where(User.role == "admin"))


def run_ask(db, site, user, client, question="Why are clicks low?", conversation_id=None):
    return ask(db, site, user, question, conversation_id, WINDOW, client, llm_settings())


def test_ask_stores_conversation_messages_and_insights(db, site, user):
    message = run_ask(db, site, user, FakeChatClient([chat_reply()]))
    assert message.role == "assistant" and message.content == "Clicks were **12**."
    assert message.suggested_questions == ["Which pages lost clicks?", "What changed on mobile?"]
    assert message.model == "primary:free"
    assert db.scalar(select(func.count()).select_from(AiConversation)) == 1
    assert db.scalar(select(func.count()).select_from(AiMessage)) == 2
    (insight,) = db.scalars(select(AiInsight)).all()
    assert (insight.source, insight.status, insight.message_id) == ("chat", "new", message.id)
    assert insight.site == DOMAIN
    conversation = db.get(AiConversation, message.conversation_id)
    assert conversation.title == "Why are clicks low?"


def test_ask_sends_last_six_messages(db, site, user):
    client = FakeChatClient([chat_reply(insights=0) for _ in range(5)])
    first = run_ask(db, site, user, client, "Question 0")
    for index in range(1, 5):
        run_ask(db, site, user, client, f"Question {index}", first.conversation_id)
    messages = client.calls[-1][1]
    assert messages[0]["role"] == "system"
    assert len(messages) == 1 + 6 + 1
    assert messages[-1] == {"role": "user", "content": "Question 4"}
    assert messages[1]["content"] == "Question 1"


def test_failed_ask_stores_nothing(db, site, user):
    with pytest.raises(LlmError):
        run_ask(db, site, user, FakeChatClient(["bad"] * 4))
    for model in (AiConversation, AiMessage, AiInsight):
        assert db.scalar(select(func.count()).select_from(model)) == 0


def test_ask_rejects_conversation_of_another_site(db, site, user):
    other = AiConversation(site="TODO-site2.example", title="other")
    db.add(other)
    db.commit()
    with pytest.raises(LookupError):
        run_ask(db, site, user, FakeChatClient([chat_reply()]), conversation_id=other.id)


def test_ungrounded_evidence_is_flagged(db, site, user):
    run_ask(db, site, user, FakeChatClient([chat_reply(value=999999)]))
    run_ask(db, site, user, FakeChatClient([chat_reply(value=12)]))
    grounded = sorted(i.evidence[0]["grounded"] for i in db.scalars(select(AiInsight)))
    assert grounded == [False, True]


def test_ground_rounds_and_ignores_text():
    numbers = {"0.1234", "12"}
    result = ground(
        [
            Evidence(metric="ctr", value=0.12, period="p"),
            Evidence(metric="clicks", value="12", period="p"),
            Evidence(metric="note", value="mobile", period="p"),
            Evidence(metric="x", value=5, period="p"),
        ],
        numbers,
    )
    assert [item["grounded"] for item in result] == [True, True, True, False]


def test_clean_question_rejects_empty_and_long():
    assert clean_question("  Why\x07 clicks?\n ") == "Why clicks?"
    with pytest.raises(ValueError):
        clean_question("\x00 ")
    with pytest.raises(ValueError):
        clean_question("a" * 2001)


def test_generate_weekly_sets_summary_and_replaces_insights(db, site):
    save_report(db, build_report(db, site, as_of=END + timedelta(days=3)))
    for _ in range(2):
        report = generate_weekly(db, site, FakeChatClient([weekly_reply()]), llm_settings())
    assert report.ai_summary.startswith("## Summary")
    weekly = db.scalars(select(AiInsight).where(AiInsight.source == "weekly")).all()
    assert len(weekly) == 2
    assert {item.report_date for item in weekly} == {report.report_date}


def test_generate_weekly_without_report_raises(db, site):
    with pytest.raises(LookupError):
        generate_weekly(db, site, FakeChatClient([weekly_reply()]), llm_settings())
    assert db.scalar(select(func.count()).select_from(WeeklyReport)) == 0


def test_weekly_reply_allows_at_most_five_insights():
    from pydantic import ValidationError

    from app.insights.prompts import WeeklyReply

    payload = json.loads(weekly_reply())
    payload["insights"] = [insight_json()] * 6
    with pytest.raises(ValidationError):
        WeeklyReply.model_validate(payload)


def test_prompt_asks_for_concise_output():
    from app.insights.prompts import SYSTEM_PROMPT

    assert "concise" in SYSTEM_PROMPT.lower()


def test_ground_checks_numbers_written_inside_text():
    numbers = {"1240", "12"}
    values = ["999999 impressions", "1,240 clicks", "12 -> 8", "−15%", "mobile only"]
    result = ground([Evidence(metric="m", value=v, period="p") for v in values], numbers)
    assert [item["grounded"] for item in result] == [False, True, False, False, True]

import json
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.insights.context import build_context, context_numbers, render_context
from app.metrics import Window
from app.models import GscDaily, Site

DOMAIN = "arlington247lockrepair.com"
END = date(2026, 10, 28)
WINDOW = Window(END - timedelta(days=27), END)


def row(page="", query="", device="", country="all", clicks=1, impressions=10, day=END):
    return GscDaily(
        site=DOMAIN,
        data_date=day,
        page=page,
        query=query,
        device=device,
        country=country,
        clicks=clicks,
        impressions=impressions,
        position=Decimal("4.5"),
    )


def site(db):
    return db.scalar(select(Site).where(Site.domain == DOMAIN))


def test_context_has_totals_and_top_lists(db, seeded):
    db.add_all(
        [
            row(clicks=7, impressions=700),
            row(clicks=3, impressions=300, day=END - timedelta(days=1)),
            row(device="MOBILE", clicks=6, impressions=600),
            row(country="usa", clicks=5, impressions=500),
            *[row(page=f"/p{i}", clicks=1, impressions=100 + i) for i in range(30)],
            row(page="/p1", query="locksmith", device="MOBILE", clicks=1, impressions=50),
        ]
    )
    db.commit()
    context = build_context(db, site(db), WINDOW)
    assert context["has_data"] is True
    assert context["totals"]["current"]["gsc"]["clicks"] == 10
    assert len(context["top_pages"]) == 25
    assert context["top_pages"][0]["page"] == "/p29"
    assert context["top_queries"][0]["query"] == "locksmith"
    assert context["devices"][0]["device"] == "MOBILE"
    assert context["countries"] == [
        {"country": "usa", "clicks": 5, "impressions": 500, "ctr": 0.01, "avg_position": 4.5}
    ]
    assert context["window"] == {"start": "2026-10-01", "end": "2026-10-28"}
    json.dumps(context)


def test_render_context_respects_limit(db, seeded):
    context = build_context(db, site(db), WINDOW)
    context["top_queries"] = [{"query": f"query number {i}", "clicks": i} for i in range(300)]
    output = render_context(context, limit=5_000)
    assert len(output) <= 5_000
    assert len(json.loads(output)["top_queries"]) < 300


def test_context_empty_site(db, seeded):
    context = build_context(db, site(db), WINDOW)
    assert context["has_data"] is False
    assert context["top_pages"] == [] and context["top_queries"] == []
    assert context["data_notes"]


def test_context_numbers_normalizes():
    assert context_numbers({"a": Decimal("0.1600"), "b": [12, {"c": 3.0}], "d": "x"}) == {
        "0.16",
        "12",
        "3",
    }


def _import(db, start, end, direct, phone="3"):
    from app.analysis.web_analytics import WebAnalyticsFile, import_web_analytics

    def tsv(*rows):
        return "\n".join("\t".join(f'"{c}"' for c in r) for r in rows) + "\n"

    files = [
        WebAnalyticsFile(
            name="Channel.csv",
            content=tsv(
                ["Channel", "Visitors", "Bounce rate", "Visit duration"],
                ["Direct", direct, "0.5", "239"],
            ),
        ),
        WebAnalyticsFile(
            name="TopPages.csv",
            content=tsv(
                ["Page", "Visitors", "Views", "Bounce rate", "Time on page"],
                [f"https://{DOMAIN}/lock-repair", "9", "12", "0.25", "61"],
            ),
        ),
        WebAnalyticsFile(
            name="OutboundLinkClicks.csv",
            content=tsv(["Event property: href", "Count", "Visitors"], ["tel:+1703", phone, "2"]),
        ),
    ]
    import_web_analytics(db, site(db), start, end, files)
    db.commit()


def test_context_without_ahrefs_has_no_block(db, seeded):
    assert "ahrefs_web_analytics" not in build_context(db, site(db), WINDOW)


def test_context_has_ahrefs_block_with_evolution(db, seeded):
    _import(db, date(2026, 9, 13), date(2026, 10, 12), "20", phone="1")
    _import(db, date(2026, 10, 13), date(2026, 11, 11), "35")
    block = build_context(db, site(db), WINDOW)["ahrefs_web_analytics"]
    assert block["period"] == {"start": "2026-10-13", "end": "2026-11-11"}
    assert block["totals"] == {"visitors": 35, "phone_clicks": 3, "pages": 1}
    assert block["top_pages"][0]["item"] == f"https://{DOMAIN}/lock-repair"
    assert block["top_pages"][0]["views"] == 12
    assert block["channels"][0]["visitors"] == 35
    assert block["previous"] == {
        "period": {"start": "2026-09-13", "end": "2026-10-12"},
        "totals": {"visitors": 20, "phone_clicks": 1, "pages": 1},
    }
    assert block["changes"]["visitors"]["change_percent"] == 75.0
    assert [item["visitors"] for item in block["history"]] == [20, 35]
    numbers = context_numbers(build_context(db, site(db), WINDOW))
    assert {"35", "75", "12", "0.25"} <= numbers

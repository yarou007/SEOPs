"""Ahrefs endpoints: Web Analytics import, latest data, changes, other uploads."""

BASE = "/api/sites/arlington/ahrefs"
DOMAIN = "arlington247lockrepair.com"


def tsv(*rows):
    return "\n".join("\t".join(f'"{cell}"' for cell in row) for row in rows) + "\n"


CHANNELS = tsv(
    ["Channel", "Visitors", "Bounce rate", "Visit duration"],
    ["Direct", "26", "0.8", "239"],
    ["Organic search", "8", "0.5", "309"],
)
TOP_PAGES = tsv(
    ["Page", "Visitors", "Views", "Bounce rate", "Time on page"],
    [f"https://{DOMAIN}/", "10", "16", "0.5", "94"],
)


def payload(start="2026-10-13", end="2026-11-11", channels=CHANNELS):
    return {
        "period_start": start,
        "period_end": end,
        "files": [
            {"name": "Channel.csv", "content": channels},
            {"name": "TopPages.csv", "content": TOP_PAGES},
            {"name": "Possible404.csv", "content": ""},
        ],
    }


def test_import_requires_manager_and_origin(client, login_as):
    url = f"{BASE}/web-analytics"
    assert client.post(url, json=payload()).status_code == 401
    login_as()  # viewer can read arlington but did not create it
    assert client.post(url, json=payload()).status_code == 403
    assert client.post("/api/sites/site2/ahrefs/web-analytics", json=payload()).status_code == 404
    login_as("admin")
    response = client.post(url, json=payload(), headers={"Origin": "https://evil.example"})
    assert response.status_code == 400


def test_import_then_get_returns_latest(client, login_as):
    login_as("admin")
    response = client.post(f"{BASE}/web-analytics", json=payload())
    assert response.status_code == 201
    body = response.json()
    assert body["period_start"] == "2026-10-13" and body["period_end"] == "2026-11-11"
    assert body["totals"] == {"visitors": 34, "phone_clicks": 0, "pages": 1}
    assert body["files"] == {"recognised": 2, "empty": ["Possible404.csv"], "unknown": []}
    login_as()
    data = client.get(BASE).json()
    assert data["web_analytics"]["totals"]["visitors"] == 34
    assert data["web_analytics"]["reports"]["top_pages"][0]["views"] == 16
    assert data["previous"] is None and data["changes"] == {}
    assert data["history"] == [
        {
            "period_start": "2026-10-13",
            "period_end": "2026-11-11",
            "visitors": 34,
            "phone_clicks": 0,
        }
    ]
    assert data["backlinks"] is None and data["internal_links"] is None


def test_second_period_gives_changes_and_history(client, login_as):
    login_as("admin")
    older = tsv(
        ["Channel", "Visitors", "Bounce rate", "Visit duration"], ["Direct", "17", "0.5", "1"]
    )
    assert (
        client.post(
            f"{BASE}/web-analytics", json=payload("2026-09-13", "2026-10-12", older)
        ).status_code
        == 201
    )
    assert client.post(f"{BASE}/web-analytics", json=payload()).status_code == 201
    data = client.get(BASE).json()
    assert data["previous"]["period_end"] == "2026-10-12"
    assert data["changes"]["visitors"] == {"now": 34, "before": 17, "change_percent": 100.0}
    assert [item["visitors"] for item in data["history"]] == [17, 34]


def test_get_unknown_site_404(client, login_as):
    login_as()
    assert client.get("/api/sites/site2/ahrefs").status_code == 404
    assert client.get("/api/sites/nope/ahrefs").status_code == 404


def test_bad_file_returns_message(client, login_as):
    login_as("admin")
    bad = tsv(
        ["Page", "Visitors", "Views", "Bounce rate", "Time on page"],
        ["https://evil.example/", "1", "1", "0.", "1"],
    )
    response = client.post(
        f"{BASE}/web-analytics",
        json={**payload(), "files": [{"name": "TopPages.csv", "content": bad}]},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "TopPages.csv: pages must belong to this website"


def test_period_order_422(client, login_as):
    login_as("admin")
    response = client.post(f"{BASE}/web-analytics", json=payload("2026-11-11", "2026-10-13"))
    assert response.status_code == 422


def test_get_includes_backlinks_upload_info(client, login_as):
    login_as("admin")
    csv = (
        "Referring page URL,Target URL\n"
        f"https://a.example/x,https://{DOMAIN}/\nhttps://b.example/y,https://{DOMAIN}/z\n"
    )
    assert (
        client.post(
            "/api/sites/arlington/axes/imports", json={"kind": "backlinks", "csv": csv}
        ).status_code
        == 201
    )
    data = client.get(BASE).json()
    assert data["backlinks"]["rows"] == 2
    assert data["backlinks"]["imported_at"]
    assert data["internal_links"] is None

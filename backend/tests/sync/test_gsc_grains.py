from datetime import date

from sqlalchemy import func, select

from app import metrics
from app.models import GscDaily, Site
from app.sync.gsc import sync_site
from app.sync.gsc_client import DETAIL, GRAINS

DAY = date(2026, 10, 19)


class HiddenQueryClient:
    def __init__(self, fail_grain=None):
        self.calls = []
        self.fail_grain = fail_grain

    def query(self, prop, start, end, offset, limit, *, dimensions=DETAIL):
        self.calls.append(dimensions)
        if dimensions == self.fail_grain:
            raise RuntimeError("aggregate failed")
        values = {
            "date": DAY.isoformat(),
            "page": "https://example.com/page",
            "query": "visible",
            "device": "mobile",
            "country": "usa",
        }
        return [
            {
                "keys": [values[key] for key in dimensions],
                "clicks": 0 if dimensions == DETAIL else 4,
                "impressions": 100 if dimensions == DETAIL else 150,
                "ctr": 0.0267,
                "position": 12,
            }
        ]


def test_independent_grains_hidden_queries_do_not_corrupt_kpis(db):
    site = Site(
        slug="example",
        domain="example.com",
        display_name="Example",
        gsc_property="sc-domain:example.com",
    )
    db.add(site)
    db.commit()
    client = HiddenQueryClient()
    assert sync_site(site, client, from_date=DAY, to_date=DAY) == 6
    assert client.calls == list(GRAINS)
    window = metrics.Window(DAY, DAY)
    assert metrics.gsc_totals(db, site.domain, window)["clicks"] == 4
    assert metrics.gsc_totals(db, site.domain, window, "MOBILE")["clicks"] == 4
    assert metrics.gsc_pages(db, site.domain, window)[0]["clicks"] == 4
    assert metrics.gsc_queries(db, site.domain, window)[0]["clicks"] == 0
    assert metrics.timeseries(db, site.domain, window)[0]["gsc_clicks"] == 4
    sync_site(site, client, from_date=DAY, to_date=DAY)
    assert db.scalar(select(func.count()).select_from(GscDaily)) == 6


def test_aggregate_failure_rolls_back_all_grains_and_checkpoint(db):
    import pytest

    from app.models import GscSyncLog

    site = Site(
        slug="example",
        domain="example.com",
        display_name="Example",
        gsc_property="sc-domain:example.com",
    )
    db.add(site)
    db.commit()
    with pytest.raises(RuntimeError, match="aggregate failed"):
        sync_site(site, HiddenQueryClient(("date", "country")), from_date=DAY, to_date=DAY)
    assert db.scalar(select(func.count()).select_from(GscDaily)) == 0
    assert db.get(GscSyncLog, site.domain).last_loaded_date is None

import logging
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from subprocess import CalledProcessError
from unittest.mock import Mock, call

import httplib2
import pytest
import requests
from conftest import run_cli
from google.analytics.data_v1beta.types import RunReportResponse
from google.api_core import exceptions
from sqlalchemy import func, select

from app.config import Settings, get_settings
from app.db import SessionLocal
from app.models import Ga4Daily, Ga4SyncLog, GscSyncLog, Site
from app.sync.ga4 import sync_site
from app.sync.ga4_client import GA4_SCOPE, FakeGa4Client, Ga4Client
from app.sync.main import main

FIRST = date(2026, 10, 16)


def row(day=FIRST, path="/services/"):
    return {
        "date": day.strftime("%Y%m%d"),
        "pagePath": path,
        "sessions": "20",
        "totalUsers": "15",
        "conversions": "2.0",
        "engagementRate": "0.12345",
    }


class RecordingClient(FakeGa4Client):
    def __init__(self, handler=None):
        self.calls = []
        self.handler = handler

    def run_report(self, property_id, start_date, end_date, offset, limit=100000):
        self.calls.append((property_id, start_date, end_date, offset, limit))
        if self.handler:
            return self.handler(property_id, start_date, end_date, offset, limit)
        return super().run_report(property_id, start_date, end_date, offset, limit)


@pytest.fixture(autouse=True)
def no_google_network(monkeypatch):
    def blocked(*args, **kwargs):
        pytest.fail("A test attempted a real Google HTTP request")

    monkeypatch.setattr(requests.Session, "request", blocked)
    monkeypatch.setattr(httplib2.Http, "request", blocked)


@pytest.fixture
def site(db):
    site = Site(
        slug="arlington",
        domain="arlington247lockrepair.com",
        display_name="Arlington",
        ga4_property_id="123456789",
    )
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


def get_log(db, site):
    db.expire_all()
    return db.get(Ga4SyncLog, site.domain)


def test_paging_150000_rows_and_batches_of_1000(site, db, monkeypatch):
    from app.sync import ga4

    sizes = []
    original_upsert = ga4._upsert_rows

    def record_upsert(session, batch):
        sizes.append(len(batch))
        original_upsert(session, batch)

    monkeypatch.setattr(ga4, "_upsert_rows", record_upsert)
    client = RecordingClient(
        lambda prop, start, end, offset, limit: (
            [row(start, f"/page/{i}/") for i in range(offset, min(offset + limit, 150000))],
            150000,
        )
    )
    assert sync_site(site, client, from_date=FIRST, to_date=FIRST) == 150000
    assert client.calls == [
        (site.ga4_property_id, FIRST, FIRST, 0, 100000),
        (site.ga4_property_id, FIRST, FIRST, 100000, 100000),
    ]
    assert sizes == [1000] * 150
    assert db.scalar(select(func.count()).select_from(Ga4Daily)) == 150000
    log = get_log(db, site)
    assert log.status == "ok"
    assert log.rows_loaded == 150000
    assert log.last_loaded_date == FIRST


@pytest.mark.parametrize("path", ["/", "/services/", "(not set)", "(other)"])
def test_mapping_dates_metrics_and_paths_as_returned(site, db, path):
    client = RecordingClient(lambda *args: ([row(path=path)], 1))
    sync_site(site, client, from_date=FIRST, to_date=FIRST)
    record = db.scalar(select(Ga4Daily))
    assert record.site == site.domain
    assert record.data_date == date(2026, 10, 16)
    assert record.page_path == path
    assert record.sessions == 20
    assert record.total_users == 15
    assert record.conversions == 2
    assert record.engagement_rate == Decimal("0.1235")
    assert record.pulled_at is not None


def test_upsert_is_idempotent_and_updates_all_metrics(site, db):
    data = row()
    client = RecordingClient(lambda *args: ([data], 1))
    sync_site(site, client, from_date=FIRST, to_date=FIRST)
    record = db.scalar(select(Ga4Daily))
    old_pulled_at = record.pulled_at
    data.update(sessions="100", totalUsers="70", conversions="9", engagementRate="0.56785")
    sync_site(site, client, from_date=FIRST, to_date=FIRST)
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(Ga4Daily)) == 1
    assert record.sessions == 100
    assert record.total_users == 70
    assert record.conversions == 9
    assert record.engagement_rate == Decimal("0.5679")
    assert record.pulled_at > old_pulled_at
    assert get_log(db, site).rows_loaded == 1


def test_resume_uses_ga4_checkpoint_independently_of_gsc(site, db):
    db.add_all(
        [
            Ga4SyncLog(site=site.domain, last_loaded_date=FIRST),
            GscSyncLog(site=site.domain, last_loaded_date=FIRST + timedelta(days=30)),
        ]
    )
    db.commit()
    client = RecordingClient()
    assert sync_site(site, client, to_date=FIRST + timedelta(days=2)) == 2
    assert client.calls == [
        (site.ga4_property_id, FIRST + timedelta(days=1), FIRST + timedelta(days=2), 0, 100000)
    ]
    assert get_log(db, site).last_loaded_date == FIRST + timedelta(days=2)
    assert db.get(GscSyncLog, site.domain).last_loaded_date == FIRST + timedelta(days=30)


def test_chunk_failure_commits_earlier_chunks_and_resumes(site, db):
    def fail_second_chunk(prop, start, end, offset, limit):
        if start == FIRST + timedelta(days=7):
            raise RuntimeError("chunk two failed")
        return FakeGa4Client().run_report(prop, start, end, offset, limit)

    end = FIRST + timedelta(days=20)
    client = RecordingClient(fail_second_chunk)
    with pytest.raises(RuntimeError, match="chunk two failed"):
        sync_site(site, client, from_date=FIRST, to_date=end)
    assert len(client.calls) == 2
    # A separate connection confirms these are committed, not merely pending ORM writes.
    with SessionLocal() as other_db:
        assert other_db.scalar(select(func.count()).select_from(Ga4Daily)) == 7
    log = get_log(db, site)
    assert log.last_loaded_date == FIRST + timedelta(days=6)
    assert log.status == "error"
    assert log.error == "RuntimeError: chunk two failed"
    assert log.rows_loaded == 7
    assert log.last_run_at is not None
    resumed = RecordingClient()
    assert sync_site(site, resumed, to_date=end) == 14
    assert resumed.calls[0][1] == FIRST + timedelta(days=7)
    log = get_log(db, site)
    assert log.last_loaded_date == end
    assert log.status == "ok"
    assert log.rows_loaded == 14
    assert log.error is None
    assert db.scalar(select(func.count()).select_from(Ga4Daily)) == 21


def test_failure_on_later_page_rolls_back_current_chunk(site, db):
    def fail_second_page(prop, start, end, offset, limit):
        if offset:
            raise RuntimeError("page two failed")
        return [row(start)], 2

    client = RecordingClient(fail_second_page)
    with pytest.raises(RuntimeError, match="page two failed"):
        sync_site(site, client, from_date=FIRST, to_date=FIRST)
    assert [request[3] for request in client.calls] == [0, 1]
    assert db.scalar(select(func.count()).select_from(Ga4Daily)) == 0
    log = get_log(db, site)
    assert log.status == "error"
    assert log.last_loaded_date is None
    assert log.rows_loaded == 0


@pytest.mark.parametrize(
    "second_page,error",
    [
        (([], 2), "empty page"),
        (([row(path="/other/")], 3), "row_count changed"),
    ],
)
def test_incomplete_or_changing_report_fails_without_advancing(site, db, second_page, error):
    client = RecordingClient(
        lambda prop, start, end, offset, limit: second_page if offset else ([row()], 2)
    )
    with pytest.raises(ValueError, match=error):
        sync_site(site, client, from_date=FIRST, to_date=FIRST)
    assert db.scalar(select(func.count()).select_from(Ga4Daily)) == 0
    assert get_log(db, site).last_loaded_date is None
    assert get_log(db, site).status == "error"


def test_empty_report_advances_checkpoint(site, db):
    client = RecordingClient(lambda *args: ([], 0))
    assert sync_site(site, client, from_date=FIRST, to_date=FIRST) == 0
    assert len(client.calls) == 1
    assert get_log(db, site).last_loaded_date == FIRST
    assert get_log(db, site).status == "ok"


def test_noop_preserves_checkpoint_and_clears_error(site, db):
    db.add(Ga4SyncLog(site=site.domain, last_loaded_date=FIRST, status="error", error="old error"))
    db.commit()
    client = RecordingClient()
    assert sync_site(site, client, to_date=FIRST) == 0
    assert client.calls == []
    log = get_log(db, site)
    assert log.last_loaded_date == FIRST
    assert log.status == "ok"
    assert log.rows_loaded == 0
    assert log.error is None


def test_missing_property_is_logged_without_calling_client(site, db, caplog):
    site.ga4_property_id = None
    db.commit()
    client = RecordingClient()
    with caplog.at_level(logging.ERROR), pytest.raises(ValueError, match="ga4_property_id not set"):
        sync_site(site, client)
    assert client.calls == []
    log = get_log(db, site)
    assert log.status == "error"
    assert log.error == "ga4_property_id not set"
    assert log.last_loaded_date is None
    assert "ga4_property_id not set" in caplog.text


def test_default_window_timezone_lag_and_seven_day_chunks(site, db, monkeypatch):
    seen_timezones = []

    def today(timezone):
        seen_timezones.append(timezone)
        return date(2026, 10, 19)

    monkeypatch.setattr("app.sync.ga4.today_in", today)
    settings = get_settings().model_copy(update={"sync_timezone": "Asia/Tokyo", "sync_lag_days": 2})
    client = RecordingClient(lambda *args: ([], 0))
    assert sync_site(site, client, settings=settings) == 0
    end = date(2026, 10, 17)
    assert seen_timezones == ["Asia/Tokyo"]
    assert client.calls[0][1] == end - timedelta(days=487)
    assert client.calls[-1][2] == end
    assert all((end - start).days < 7 for _, start, end, _, _ in client.calls)
    assert all(
        current[2] + timedelta(days=1) == following[1]
        for current, following in zip(client.calls, client.calls[1:], strict=False)
    )
    assert get_log(db, site).last_loaded_date == end


@pytest.fixture
def google_transport(monkeypatch):
    sdk = Mock()
    load = Mock(return_value=Mock())
    constructor = Mock(return_value=sdk)
    sleep = Mock()
    monkeypatch.setattr(
        "app.sync.ga4_client.service_account.Credentials.from_service_account_file", load
    )
    monkeypatch.setattr("app.sync.ga4_client.BetaAnalyticsDataClient", constructor)
    monkeypatch.setattr("app.sync.ga4_client.time.sleep", sleep)
    sdk.run_report.return_value = RunReportResponse(
        row_count=1,
        rows=[
            {
                "dimension_values": [{"value": "20261016"}, {"value": "(not set)"}],
                "metric_values": [{"value": value} for value in ["20", "15", "2.0", "0.12345"]],
            }
        ],
    )
    return sdk, load, constructor, sleep


def test_google_request_scope_and_parsed_plain_dicts(google_transport):
    sdk, load, constructor, sleep = google_transport
    client = Ga4Client(Path("/test/service-account.json"))
    rows, count = client.run_report("123456789", FIRST, FIRST, 100000, 50000)
    assert rows == [row(path="(not set)")]
    assert type(rows[0]) is dict
    assert count == 1
    load.assert_called_once_with("/test/service-account.json", scopes=[GA4_SCOPE])
    constructor.assert_called_once_with(credentials=load.return_value, transport="rest")
    request = sdk.run_report.call_args.kwargs["request"]
    assert request.property == "properties/123456789"
    assert [dimension.name for dimension in request.dimensions] == ["date", "pagePath"]
    assert [metric.name for metric in request.metrics] == [
        "sessions",
        "totalUsers",
        "conversions",
        "engagementRate",
    ]
    assert request.date_ranges[0].start_date == "2026-10-16"
    assert request.date_ranges[0].end_date == "2026-10-16"
    assert [order.dimension.dimension_name for order in request.order_bys] == ["date", "pagePath"]
    assert request.offset == 100000
    assert request.limit == 50000
    assert sdk.run_report.call_args.kwargs["retry"] is None
    assert sdk.run_report.call_args.kwargs["timeout"] == 60
    sleep.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [
        exceptions.TooManyRequests,
        exceptions.InternalServerError,
        exceptions.ServiceUnavailable,
    ],
)
def test_retry_twice_then_success(google_transport, error):
    sdk, load, constructor, sleep = google_transport
    sdk.run_report.side_effect = [error("test"), error("test"), sdk.run_report.return_value]
    rows, count = Ga4Client(Path("/test/service-account.json")).run_report("123", FIRST, FIRST, 0)
    assert count == 1
    assert len(rows) == 1
    assert sdk.run_report.call_count == 3
    assert sleep.call_args_list == [call(1), call(2)]


def test_retry_exhaustion_is_five_attempts(google_transport):
    sdk, load, constructor, sleep = google_transport
    sdk.run_report.side_effect = exceptions.TooManyRequests("test")
    with pytest.raises(exceptions.TooManyRequests):
        Ga4Client(Path("/test/service-account.json")).run_report("123", FIRST, FIRST, 0)
    assert sdk.run_report.call_count == 5
    assert sleep.call_args_list == [call(1), call(2), call(4), call(8)]


@pytest.mark.parametrize(
    "error",
    [
        exceptions.BadRequest,
        exceptions.Unauthorized,
        exceptions.Forbidden,
        exceptions.NotFound,
        ValueError,
    ],
)
def test_other_errors_fail_immediately(google_transport, error):
    sdk, load, constructor, sleep = google_transport
    sdk.run_report.side_effect = error("test")
    with pytest.raises(error):
        Ga4Client(Path("/test/service-account.json")).run_report("123", FIRST, FIRST, 0)
    assert sdk.run_report.call_count == 1
    sleep.assert_not_called()


def test_credentials_are_never_logged(site, db, caplog, google_transport):
    sdk, load, constructor, sleep = google_transport
    load.side_effect = ValueError("PRIVATE-KEY-CONTENTS")
    with pytest.raises(ValueError, match="Unable to load GA4 service account file"):
        sync_site(site, Ga4Client(Path("/test/key.json")), from_date=FIRST, to_date=FIRST)
    assert "PRIVATE-KEY-CONTENTS" not in caplog.text
    assert "PRIVATE-KEY-CONTENTS" not in get_log(db, site).error
    constructor.assert_not_called()


def test_credentials_fall_back_to_gsc_unless_explicitly_set():
    settings = Settings(
        _env_file=None,
        ga4_service_account_file=None,
        gsc_service_account_file=Path("/test/gsc.json"),
    )
    assert settings.ga4_service_account_file == Path("/test/gsc.json")
    settings = Settings(
        _env_file=None,
        ga4_service_account_file=Path("/test/ga4.json"),
        gsc_service_account_file=Path("/test/gsc.json"),
    )
    assert settings.ga4_service_account_file == Path("/test/ga4.json")


def test_all_continues_after_failure_and_skips_inactive(site, db, monkeypatch):
    db.add_all(
        [
            Site(
                slug="site2", domain="site2.example", display_name="Site 2", ga4_property_id="bad"
            ),
            Site(
                slug="site3", domain="site3.example", display_name="Site 3", ga4_property_id="good"
            ),
            Site(slug="site4", domain="site4.example", display_name="Site 4", active=False),
        ]
    )
    db.commit()

    def fail_second(prop, start, end, offset, limit):
        if prop == "bad":
            raise RuntimeError("one site failed")
        return [row(start)], 1

    client = RecordingClient(fail_second)
    monkeypatch.delenv("SYNC_FAKE_CLIENT", raising=False)
    monkeypatch.setattr("app.sync.ga4_client.Ga4Client", lambda path: client)
    assert main(["ga4", "--all", "--from", "2026-10-16", "--to", "2026-10-16"]) == 1
    assert [request[0] for request in client.calls] == [site.ga4_property_id, "bad", "good"]
    db.expire_all()
    logs = {log.site: log for log in db.scalars(select(Ga4SyncLog))}
    assert logs[site.domain].status == "ok"
    assert logs["site2.example"].status == "error"
    assert logs["site3.example"].status == "ok"
    assert "site4.example" not in logs


@pytest.mark.parametrize(
    "flag,is_fake", [(None, False), ("0", False), ("true", False), ("1", True)]
)
def test_fake_mode_requires_explicit_env_flag(site, monkeypatch, flag, is_fake):
    if flag is None:
        monkeypatch.delenv("SYNC_FAKE_CLIENT", raising=False)
    else:
        monkeypatch.setenv("SYNC_FAKE_CLIENT", flag)
    seen = []
    monkeypatch.setattr(
        "app.sync.ga4.sync_site", lambda site, client, **kwargs: seen.append(client)
    )
    assert main(["ga4", "--site", "arlington"]) == 0
    assert isinstance(seen[0], FakeGa4Client if is_fake else Ga4Client)


def test_cli_fake_mode_writes_real_rows(site, db, monkeypatch):
    monkeypatch.setenv("SYNC_FAKE_CLIENT", "1")
    result = run_cli(
        "app.sync", "ga4", "--site", "arlington", "--from", "2026-10-16", "--to", "2026-10-17"
    )
    assert result.returncode == 0
    assert "test-only synthetic data" in result.stderr
    assert db.scalar(select(func.count()).select_from(Ga4Daily)) == 2
    log = get_log(db, site)
    assert log.status == "ok"
    assert log.rows_loaded == 2
    assert log.last_loaded_date == FIRST + timedelta(days=1)


def test_cli_all_missing_property_exits_one_and_continues(site, db, monkeypatch):
    site.slug = "zzz"
    db.add(Site(slug="aaa", domain="missing.example", display_name="Missing"))
    db.commit()
    monkeypatch.setenv("SYNC_FAKE_CLIENT", "1")
    with pytest.raises(CalledProcessError) as error:
        run_cli("app.sync", "ga4", "--all", "--from", "2026-10-16", "--to", "2026-10-16")
    assert error.value.returncode == 1
    assert "ga4_property_id not set" in error.value.stderr
    assert get_log(db, site).status == "ok"
    assert db.get(Ga4SyncLog, "missing.example").status == "error"


def test_cli_help_and_top_level_commands_need_no_settings(monkeypatch):
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    result = run_cli("app.sync", "ga4", "--help")
    for option in ["--site", "--all", "--from", "--to"]:
        assert option in result.stdout
    top_level = run_cli("app.sync", "--help")
    assert "gsc" in top_level.stdout
    assert "ga4" in top_level.stdout

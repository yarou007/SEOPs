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
from googleapiclient.errors import HttpError
from pydantic import ValidationError
from sqlalchemy import func, select

from app.config import Settings, get_settings
from app.models import GscDaily, GscSyncLog, Site
from app.sync.gsc import sync_site
from app.sync.gsc_client import DETAIL, GSC_SCOPE, FakeGscClient, GscClient
from app.sync.main import main

FIRST = date(2026, 10, 1)


def row(day=FIRST, index=0):
    return {
        "keys": [
            day.isoformat(),
            f"https://arlington247lockrepair.com/{index}",
            "locksmith",
            "mobile",
        ],
        "clicks": 3.0,
        "impressions": 20.0,
        "ctr": 0.12345,
        "position": 2.345,
    }


class RecordingClient(FakeGscClient):
    def __init__(self, handler=None):
        self.calls = []
        self.handler = handler

    def query(
        self, site_property, start_date, end_date, start_row, row_limit=25000, *, dimensions=DETAIL
    ):
        if dimensions != DETAIL:
            return []
        self.calls.append((site_property, start_date, end_date, start_row, row_limit))
        if self.handler:
            return self.handler(site_property, start_date, end_date, start_row, row_limit)
        return super().query(site_property, start_date, end_date, start_row, row_limit)


@pytest.fixture(autouse=True)
def no_google_network(monkeypatch):
    def blocked(*args, **kwargs):
        pytest.fail("A test attempted a real Google HTTP request")

    monkeypatch.setattr(httplib2.Http, "request", blocked)
    monkeypatch.setattr(requests.Session, "request", blocked)


@pytest.fixture
def site(db):
    site = Site(
        slug="arlington",
        domain="arlington247lockrepair.com",
        display_name="Arlington",
        gsc_property="sc-domain:arlington247lockrepair.com",
    )
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


def get_log(db, site):
    db.expire_all()
    return db.get(GscSyncLog, site.domain)


def test_paging_25000_plus_10_and_batches_of_1000(site, db, monkeypatch):
    from app.sync import gsc

    sizes = []
    original_upsert = gsc._upsert_rows

    def record_upsert(session, batch):
        sizes.append(len(batch))
        original_upsert(session, batch)

    monkeypatch.setattr(gsc, "_upsert_rows", record_upsert)
    client = RecordingClient(
        lambda prop, start, end, offset, limit: [
            row(start, i) for i in range(offset, min(offset + limit, 25010))
        ]
    )
    assert sync_site(site, client, from_date=FIRST, to_date=FIRST) == 25010
    assert [request[3] for request in client.calls] == [0, 25000]
    assert len(client.calls) == 2
    assert sizes == [1000] * 25 + [10]
    assert db.scalar(select(func.count()).select_from(GscDaily)) == 25010
    log = get_log(db, site)
    assert log.rows_loaded == 25010
    assert log.last_loaded_date == FIRST
    assert log.status == "ok"


def test_upsert_idempotency_updates_metrics_and_pulled_at(site, db):
    first_row = row()
    client = RecordingClient(lambda *args: [first_row])
    sync_site(site, client, from_date=FIRST, to_date=FIRST)
    record = db.scalar(select(GscDaily))
    old_pulled_at = record.pulled_at
    first_row.update(clicks=9.0, impressions=90.0, ctr=0.1, position=8.675)
    sync_site(site, client, from_date=FIRST, to_date=FIRST)
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(GscDaily)) == 1
    assert record.clicks == 9
    assert record.impressions == 90
    assert record.ctr == Decimal("0.1000")
    assert record.position == Decimal("8.68")
    assert record.pulled_at > old_pulled_at
    assert get_log(db, site).rows_loaded == 1


def test_mapping_uses_domain_and_numeric_precision(site, db):
    client = RecordingClient(lambda *args: [row()])
    sync_site(site, client, from_date=FIRST, to_date=FIRST)
    record = db.scalar(select(GscDaily))
    assert record.site == site.domain
    assert record.site != site.slug
    assert record.data_date == FIRST
    assert isinstance(record.data_date, date)
    assert record.device == "MOBILE"
    assert record.country == "all"
    assert record.clicks == 3
    assert record.impressions == 20
    assert record.ctr == Decimal("0.1235")
    assert record.position == Decimal("2.35")
    assert record.pulled_at is not None


def test_resume_starts_day_after_checkpoint(site, db):
    db.add(GscSyncLog(site=site.domain, last_loaded_date=FIRST, status="ok"))
    db.commit()
    client = RecordingClient()
    sync_site(site, client, to_date=FIRST + timedelta(days=2))
    assert client.calls == [
        (site.gsc_property, FIRST + timedelta(days=1), FIRST + timedelta(days=2), 0, 25000)
    ]
    assert get_log(db, site).last_loaded_date == FIRST + timedelta(days=2)


def test_first_run_window_uses_configured_timezone_and_lag(site, db, monkeypatch):
    seen_timezones = []

    def today(timezone):
        seen_timezones.append(timezone)
        return date(2026, 10, 19)

    monkeypatch.setattr("app.sync.gsc.today_in", today)
    settings = get_settings().model_copy(
        update={"sync_timezone": "Pacific/Auckland", "sync_lag_days": 5}
    )
    client = RecordingClient(lambda *args: [])
    assert sync_site(site, client, settings=settings) == 0
    expected_end = date(2026, 10, 14)
    assert seen_timezones == ["Pacific/Auckland"]
    assert client.calls[0][1] == expected_end - timedelta(days=487)
    assert client.calls[-1][2] == expected_end
    assert all((end - start).days < 7 for _, start, end, _, _ in client.calls)
    assert all(
        current[2] + timedelta(days=1) == following[1]
        for current, following in zip(client.calls, client.calls[1:], strict=False)
    )
    assert get_log(db, site).last_loaded_date == expected_end


def test_noop_preserves_checkpoint_and_records_zero(site, db):
    db.add(
        GscSyncLog(
            site=site.domain,
            last_loaded_date=FIRST,
            rows_loaded=99,
            status="error",
            error="old error",
        )
    )
    db.commit()
    client = RecordingClient()
    assert sync_site(site, client, to_date=FIRST) == 0
    assert client.calls == []
    log = get_log(db, site)
    assert log.last_loaded_date == FIRST
    assert log.status == "ok"
    assert log.rows_loaded == 0
    assert log.error is None
    assert log.last_run_at is not None


def test_chunk_failure_preserves_first_chunk_and_resume_has_no_gap(site, db):
    def fail_second_chunk(prop, start, end, offset, limit):
        if start == FIRST + timedelta(days=7):
            raise RuntimeError("chunk two failed")
        return [row(start)]

    end = FIRST + timedelta(days=20)
    client = RecordingClient(fail_second_chunk)
    with pytest.raises(RuntimeError, match="chunk two failed"):
        sync_site(site, client, from_date=FIRST, to_date=end)
    assert len(client.calls) == 2
    assert db.scalar(select(func.count()).select_from(GscDaily)) == 1
    log = get_log(db, site)
    assert log.last_loaded_date == FIRST + timedelta(days=6)
    assert log.status == "error"
    assert log.error == "RuntimeError: chunk two failed"
    assert log.rows_loaded == 1
    assert log.last_run_at is not None
    resumed = RecordingClient()
    assert sync_site(site, resumed, to_date=end) == 14
    assert resumed.calls[0][1] == FIRST + timedelta(days=7)
    log = get_log(db, site)
    assert log.last_loaded_date == end
    assert log.status == "ok"
    assert log.rows_loaded == 14
    assert log.error is None


def test_page_failure_rolls_back_rows_already_written_in_current_chunk(site, db):
    def fail_next_page(prop, start, end, offset, limit):
        if offset:
            raise RuntimeError("page two failed")
        return [row(start, i) for i in range(limit)]

    client = RecordingClient(fail_next_page)
    with pytest.raises(RuntimeError, match="page two failed"):
        sync_site(site, client, from_date=FIRST, to_date=FIRST)
    assert db.scalar(select(func.count()).select_from(GscDaily)) == 0
    log = get_log(db, site)
    assert log.last_loaded_date is None
    assert log.status == "error"
    assert log.rows_loaded == 0


def test_missing_gsc_property_records_exact_error(site, db, caplog):
    site.gsc_property = None
    db.commit()
    client = RecordingClient()
    with caplog.at_level(logging.ERROR), pytest.raises(ValueError, match="gsc_property not set"):
        sync_site(site, client)
    assert client.calls == []
    assert get_log(db, site).error == "gsc_property not set"
    assert get_log(db, site).status == "error"
    assert "gsc_property not set" in caplog.text


def test_error_message_is_bounded_and_checkpoint_unchanged(site, db):
    db.add(GscSyncLog(site=site.domain, last_loaded_date=FIRST))
    db.commit()

    def fail(*args):
        raise RuntimeError("x" * 1000)

    with pytest.raises(RuntimeError):
        sync_site(site, RecordingClient(fail), to_date=FIRST + timedelta(days=1))
    log = get_log(db, site)
    assert len(log.error) == 500
    assert log.last_loaded_date == FIRST
    assert log.rows_loaded == 0


def test_historical_override_does_not_rewind_checkpoint(site, db):
    later = FIRST + timedelta(days=30)
    db.add(GscSyncLog(site=site.domain, last_loaded_date=later))
    db.commit()
    sync_site(site, RecordingClient(), from_date=FIRST, to_date=FIRST)
    assert get_log(db, site).last_loaded_date == later


def test_failed_first_run_without_checkpoint_retries_initial_window(site, db, monkeypatch):
    monkeypatch.setattr("app.sync.gsc.today_in", lambda timezone: date(2026, 10, 19))
    # This is the log state left when the very first chunk or missing-property run fails.
    db.add(GscSyncLog(site=site.domain, status="error", last_loaded_date=None))
    db.commit()
    client = RecordingClient(lambda *args: [])
    sync_site(site, client)
    assert client.calls[0][1] == date(2026, 10, 16) - timedelta(days=487)


def http_error(status):
    return HttpError(httplib2.Response({"status": str(status)}), b'{"error":{"message":"test"}}')


@pytest.fixture
def google_transport(monkeypatch):
    service = Mock()
    credentials = Mock()
    load = Mock(return_value=credentials)
    build = Mock(return_value=service)
    monkeypatch.setattr(
        "app.sync.gsc_client.service_account.Credentials.from_service_account_file", load
    )
    monkeypatch.setattr("app.sync.gsc_client.build", build)
    sleep = Mock()
    monkeypatch.setattr("app.sync.gsc_client.time.sleep", sleep)
    execute = service.searchanalytics.return_value.query.return_value.execute
    execute.return_value = {"rows": [row()]}
    return service, load, build, sleep, execute


def test_google_query_body_scopes_and_raw_rows(google_transport):
    service, load, build, sleep, execute = google_transport
    client = GscClient(Path("/test/service-account.json"))
    assert client.query("sc-domain:example.com", FIRST, FIRST, 25000) == [row()]
    load.assert_called_once_with("/test/service-account.json", scopes=[GSC_SCOPE])
    build.assert_called_once_with(
        "searchconsole",
        "v1",
        credentials=load.return_value,
        cache_discovery=False,
        static_discovery=True,
    )
    service.searchanalytics.return_value.query.assert_called_once_with(
        siteUrl="sc-domain:example.com",
        body={
            "startDate": "2026-10-01",
            "endDate": "2026-10-01",
            "dimensions": ["date", "page", "query", "device"],
            "aggregationType": "byPage",
            "type": "web",
            "dataState": "final",
            "startRow": 25000,
            "rowLimit": 25000,
        },
    )
    execute.assert_called_once_with(num_retries=0)
    sleep.assert_not_called()


def test_google_empty_rows_and_custom_row_limit(google_transport):
    service, load, build, sleep, execute = google_transport
    execute.return_value = {}
    assert GscClient(Path("/test/service-account.json")).query("test", FIRST, FIRST, 0, 10) == []
    assert service.searchanalytics.return_value.query.call_args.kwargs["body"]["rowLimit"] == 10


@pytest.mark.parametrize("status", [429, 500, 503])
def test_retry_twice_then_success(google_transport, status):
    service, load, build, sleep, execute = google_transport
    execute.side_effect = [http_error(status), http_error(status), {"rows": [row()]}]
    assert GscClient(Path("/test/service-account.json")).query("test", FIRST, FIRST, 0) == [row()]
    assert execute.call_count == 3
    assert sleep.call_args_list == [call(1), call(2)]


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_other_4xx_fail_immediately(google_transport, status):
    service, load, build, sleep, execute = google_transport
    execute.side_effect = http_error(status)
    with pytest.raises(HttpError):
        GscClient(Path("/test/service-account.json")).query("test", FIRST, FIRST, 0)
    assert execute.call_count == 1
    sleep.assert_not_called()


def test_retry_exhaustion_is_five_attempts(google_transport):
    service, load, build, sleep, execute = google_transport
    execute.side_effect = http_error(429)
    with pytest.raises(HttpError):
        GscClient(Path("/test/service-account.json")).query("test", FIRST, FIRST, 0)
    assert execute.call_count == 5
    assert sleep.call_args_list == [call(1), call(2), call(4), call(8)]


def test_credential_contents_are_never_logged(site, db, caplog, google_transport):
    service, load, build, sleep, execute = google_transport
    load.side_effect = ValueError("PRIVATE-KEY-CONTENTS")
    with pytest.raises(ValueError, match="Unable to load GSC service account file"):
        sync_site(
            site, GscClient(Path("/test/service-account.json")), from_date=FIRST, to_date=FIRST
        )
    assert "PRIVATE-KEY-CONTENTS" not in caplog.text
    assert "PRIVATE-KEY-CONTENTS" not in get_log(db, site).error
    build.assert_not_called()


def test_all_continues_after_failure_and_ignores_inactive(site, db, monkeypatch):
    db.add_all(
        [
            Site(slug="site2", domain="site2.example", display_name="Site 2", gsc_property="bad"),
            Site(slug="site3", domain="site3.example", display_name="Site 3", gsc_property="good"),
            Site(slug="site4", domain="site4.example", display_name="Site 4", active=False),
        ]
    )
    db.commit()

    def fail_second(prop, start, end, offset, limit):
        if prop == "bad":
            raise RuntimeError("one site failed")
        return [row(start)]

    client = RecordingClient(fail_second)
    monkeypatch.delenv("SYNC_FAKE_CLIENT", raising=False)
    monkeypatch.setattr("app.sync.gsc_client.GscClient", lambda path: client)
    assert main(["gsc", "--all", "--from", "2026-10-01", "--to", "2026-10-01"]) == 1
    assert [request[0] for request in client.calls] == [site.gsc_property, "bad", "good"]
    db.expire_all()
    logs = {log.site: log for log in db.scalars(select(GscSyncLog))}
    assert logs[site.domain].status == "ok"
    assert logs["site2.example"].status == "error"
    assert logs["site3.example"].status == "ok"
    assert "site4.example" not in logs


@pytest.mark.parametrize(
    "flag,is_fake", [(None, False), ("0", False), ("true", False), ("1", True)]
)
def test_fake_mode_requires_explicit_env_flag(site, monkeypatch, flag, is_fake):
    seen = []
    if flag is None:
        monkeypatch.delenv("SYNC_FAKE_CLIENT", raising=False)
    else:
        monkeypatch.setenv("SYNC_FAKE_CLIENT", flag)
    monkeypatch.setattr(
        "app.sync.gsc.sync_site", lambda site, client, **kwargs: seen.append(client)
    )
    assert main(["gsc", "--site", "arlington"]) == 0
    assert isinstance(seen[0], FakeGscClient if is_fake else GscClient)


def test_cli_fake_mode_runs_real_upserts(site, db, monkeypatch):
    monkeypatch.setenv("SYNC_FAKE_CLIENT", "1")
    result = run_cli(
        "app.sync", "gsc", "--site", "arlington", "--from", "2026-10-01", "--to", "2026-10-02"
    )
    assert result.returncode == 0
    assert "test-only synthetic data" in result.stderr
    assert db.scalar(select(func.count()).select_from(GscDaily)) == 12
    log = get_log(db, site)
    assert log.status == "ok"
    assert log.last_loaded_date == date(2026, 10, 2)
    assert log.rows_loaded == 12


def test_cli_all_missing_property_exits_one_and_continues(site, db, monkeypatch):
    # Sort the missing-property site first, so the second site proves continuation.
    site.slug = "zzz"
    db.add(Site(slug="aaa", domain="missing.example", display_name="Missing"))
    db.commit()
    monkeypatch.setenv("SYNC_FAKE_CLIENT", "1")
    with pytest.raises(CalledProcessError) as error:
        run_cli("app.sync", "gsc", "--all", "--from", "2026-10-01", "--to", "2026-10-01")
    assert error.value.returncode == 1
    assert "gsc_property not set" in error.value.stderr
    assert get_log(db, site).status == "ok"
    assert db.get(GscSyncLog, "missing.example").status == "error"


def test_cli_help_needs_no_settings(monkeypatch):
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    result = run_cli("app.sync", "gsc", "--help")
    assert "--site" in result.stdout
    assert "--all" in result.stdout
    assert "--from" in result.stdout
    assert "--to" in result.stdout


def test_cli_rejects_invalid_range():
    with pytest.raises(SystemExit) as error:
        main(["gsc", "--site", "arlington", "--from", "2026-10-02", "--to", "2026-10-01"])
    assert error.value.code == 2


def test_cli_unknown_site_returns_one():
    assert main(["gsc", "--site", "unknown"]) == 1


def test_sync_configuration_rejects_invalid_values():
    with pytest.raises(ValidationError):
        Settings(sync_timezone="not/a-timezone")
    with pytest.raises(ValidationError):
        Settings(sync_lag_days=-1)

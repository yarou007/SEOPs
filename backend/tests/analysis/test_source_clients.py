from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call

import httplib2
import pytest
from google.api_core.exceptions import TooManyRequests
from googleapiclient.errors import HttpError

from app.analysis.source_clients import Ga4AxisClient, GscInspectionClient

DAY = date(2026, 10, 19)


def test_sitemaps_and_inspection_transport_are_read_only(monkeypatch):
    service = Mock()
    service.sitemaps.return_value.list.return_value.execute.return_value = {
        "sitemap": [{"path": "https://example.com/sitemap.xml"}]
    }
    inspection = service.urlInspection.return_value.index.return_value.inspect.return_value
    inspection.execute.return_value = {
        "inspectionResult": {"indexStatusResult": {"verdict": "PASS"}}
    }
    client = GscInspectionClient(Path("/unused"))
    monkeypatch.setattr(client, "_get_service", lambda: service)
    assert client.sitemaps("sc-domain:example.com")[0]["path"].endswith("sitemap.xml")
    assert client.inspect("sc-domain:example.com", "https://example.com/") == {"verdict": "PASS"}
    service.sitemaps.return_value.list.assert_called_once_with(siteUrl="sc-domain:example.com")
    service.urlInspection.return_value.index.return_value.inspect.assert_called_once_with(
        body={
            "siteUrl": "sc-domain:example.com",
            "inspectionUrl": "https://example.com/",
            "languageCode": "en-US",
        }
    )


@pytest.mark.parametrize("status,retries", [(429, 3), (503, 3), (403, 1)])
def test_inspection_retry_bounded(monkeypatch, status, retries):
    error = HttpError(httplib2.Response({"status": str(status)}), b"{}")
    request = Mock()
    request.execute.side_effect = [error, error, {"ok": True}]
    sleep = Mock()
    monkeypatch.setattr("app.analysis.source_clients.time.sleep", sleep)
    client = GscInspectionClient(None)
    if retries == 1:
        with pytest.raises(HttpError):
            client._execute(lambda: request)
    else:
        assert client._execute(lambda: request) == {"ok": True}
        assert sleep.call_args_list == [call(1), call(2)]
    assert request.execute.call_count == retries


def test_ga4_axis_report_retries_pages_and_filters_event(monkeypatch):
    def value(text):
        return SimpleNamespace(value=text)

    row = SimpleNamespace(dimension_values=[value("call_click")], metric_values=[value("2")])
    fake = Mock()
    fake.run_report.side_effect = [
        TooManyRequests("test"),
        TooManyRequests("test"),
        SimpleNamespace(rows=[row], row_count=2),
        SimpleNamespace(rows=[row], row_count=2),
    ]
    sleep = Mock()
    monkeypatch.setattr("app.analysis.source_clients.time.sleep", sleep)
    client = Ga4AxisClient(None)
    monkeypatch.setattr(client, "_get_client", lambda: fake)
    result = client.report("123", DAY, DAY, ["eventName"], ["eventCount"], event="call_click")
    assert result == [{"eventName": "call_click", "eventCount": "2"}] * 2
    assert sleep.call_args_list == [call(1), call(2)]
    requests = [item.kwargs["request"] for item in fake.run_report.call_args_list]
    assert [request.offset for request in requests] == [0, 0, 0, 1]
    assert requests[0].property == "properties/123"
    assert requests[0].dimension_filter.filter.string_filter.value == "call_click"


def test_ga4_axis_report_rejects_truncated_paging(monkeypatch):
    fake = Mock()
    fake.run_report.return_value = SimpleNamespace(rows=[], row_count=2)
    client = Ga4AxisClient(None)
    monkeypatch.setattr(client, "_get_client", lambda: fake)
    with pytest.raises(ValueError, match="before row_count"):
        client.report("123", DAY, DAY, ["operatingSystem"], ["sessions"])

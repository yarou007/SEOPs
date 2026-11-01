"""Read-only Google adapters for explicitly collected axis evidence."""

import time
from datetime import date
from typing import Protocol

from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Filter,
    FilterExpression,
    Metric,
    RunReportRequest,
)
from google.api_core.exceptions import GoogleAPICallError
from googleapiclient.errors import HttpError

from app.sync.ga4_client import Ga4Client
from app.sync.gsc_client import GscClient


class InspectionClient(Protocol):
    def sitemaps(self, site_property: str) -> list[dict]: ...
    def inspect(self, site_property: str, url: str) -> dict: ...


class GscInspectionClient(GscClient):
    def _execute(self, make_request):
        for attempt in range(5):
            try:
                return make_request().execute(num_retries=0)
            except HttpError as exc:
                if attempt == 4 or not (exc.resp.status == 429 or 500 <= exc.resp.status < 600):
                    raise
                time.sleep(2**attempt)
        raise AssertionError("unreachable")

    def sitemaps(self, site_property: str) -> list[dict]:
        return self._execute(
            lambda: self._get_service().sitemaps().list(siteUrl=site_property)
        ).get("sitemap", [])

    def inspect(self, site_property: str, url: str) -> dict:
        result = self._execute(
            lambda: (
                self._get_service()
                .urlInspection()
                .index()
                .inspect(
                    body={"siteUrl": site_property, "inspectionUrl": url, "languageCode": "en-US"}
                )
            )
        )
        return result.get("inspectionResult", {}).get("indexStatusResult", {})


class AxisGa4Client(Protocol):
    def report(
        self,
        property_id: str,
        start: date,
        end: date,
        dimensions: list[str],
        metrics: list[str],
        event: str | None = None,
    ) -> list[dict]: ...


class Ga4AxisClient(Ga4Client):
    def report(
        self,
        property_id: str,
        start: date,
        end: date,
        dimensions: list[str],
        metrics: list[str],
        event: str | None = None,
    ) -> list[dict]:
        rows = []
        while True:
            request = RunReportRequest(
                property=f"properties/{property_id}",
                dimensions=[Dimension(name=name) for name in dimensions],
                metrics=[Metric(name=name) for name in metrics],
                date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
                offset=len(rows),
                limit=100_000,
            )
            if event:
                request.dimension_filter = FilterExpression(
                    filter=Filter(
                        field_name="eventName",
                        string_filter=Filter.StringFilter(
                            value=event,
                            match_type=Filter.StringFilter.MatchType.EXACT,
                            case_sensitive=True,
                        ),
                    )
                )
            for attempt in range(5):
                try:
                    response = self._get_client().run_report(
                        request=request, retry=None, timeout=60
                    )
                    break
                except GoogleAPICallError as exc:
                    if (
                        attempt == 4
                        or exc.code is None
                        or not (exc.code == 429 or 500 <= exc.code < 600)
                    ):
                        raise
                    time.sleep(2**attempt)
            page = [
                {
                    **{name: row.dimension_values[i].value for i, name in enumerate(dimensions)},
                    **{name: row.metric_values[i].value for i, name in enumerate(metrics)},
                }
                for row in response.rows
            ]
            rows.extend(page)
            if len(rows) >= response.row_count:
                return rows
            if not page:
                raise ValueError("GA4 axis report ended before row_count")

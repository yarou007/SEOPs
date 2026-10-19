"""Google Analytics Data API transport and explicit offline test implementation."""

import time
from datetime import date, timedelta
from pathlib import Path
from typing import Protocol, TypedDict

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    OrderBy,
    RunReportRequest,
)
from google.api_core.exceptions import GoogleAPICallError
from google.oauth2 import service_account

GA4_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"
PAGE_SIZE = 100000


class Ga4Row(TypedDict):
    date: str
    pagePath: str
    sessions: str
    totalUsers: str
    conversions: str
    engagementRate: str


class Ga4QueryClient(Protocol):
    def run_report(
        self,
        property_id: str,
        start_date: date,
        end_date: date,
        offset: int,
        limit: int = PAGE_SIZE,
    ) -> tuple[list[Ga4Row], int]: ...


class Ga4Client:
    def __init__(self, service_account_file: Path | None):
        self._service_account_file = service_account_file
        self._client: BetaAnalyticsDataClient | None = None

    def _get_client(self) -> BetaAnalyticsDataClient:
        if self._client is None:
            if self._service_account_file is None:
                raise ValueError(
                    "GA4_SERVICE_ACCOUNT_FILE (or GSC_SERVICE_ACCOUNT_FILE) is not set"
                )
            try:
                credentials = service_account.Credentials.from_service_account_file(
                    str(self._service_account_file),
                    scopes=[GA4_SCOPE],
                )
            except Exception:
                raise ValueError("Unable to load GA4 service account file") from None
            try:
                # REST exposes HTTP status errors and allows one explicit retry policy.
                self._client = BetaAnalyticsDataClient(credentials=credentials, transport="rest")
            except Exception:
                raise RuntimeError("Unable to initialize GA4 API client") from None
        return self._client

    def run_report(
        self,
        property_id: str,
        start_date: date,
        end_date: date,
        offset: int,
        limit: int = PAGE_SIZE,
    ) -> tuple[list[Ga4Row], int]:
        client = self._get_client()
        request = RunReportRequest(
            property=f"properties/{property_id}",
            dimensions=[Dimension(name="date"), Dimension(name="pagePath")],
            metrics=[
                Metric(name=name)
                for name in [
                    "sessions",
                    "totalUsers",
                    "conversions",
                    "engagementRate",
                ]
            ],
            date_ranges=[
                DateRange(start_date=start_date.isoformat(), end_date=end_date.isoformat())
            ],
            order_bys=[
                OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name=name))
                for name in ["date", "pagePath"]
            ],
            offset=offset,
            limit=limit,
        )
        for attempt in range(5):
            try:
                response = client.run_report(request=request, retry=None, timeout=60)
                return [
                    {
                        "date": row.dimension_values[0].value,
                        "pagePath": row.dimension_values[1].value,
                        "sessions": row.metric_values[0].value,
                        "totalUsers": row.metric_values[1].value,
                        "conversions": row.metric_values[2].value,
                        "engagementRate": row.metric_values[3].value,
                    }
                    for row in response.rows
                ], response.row_count
            except GoogleAPICallError as exc:
                status = exc.code
                if attempt == 4 or status is None or not (status == 429 or 500 <= status < 600):
                    raise
                time.sleep(2**attempt)
        raise AssertionError("unreachable")


class FakeGa4Client:
    """One synthetic path per date; never reads credentials or contacts Google."""

    def run_report(
        self,
        property_id: str,
        start_date: date,
        end_date: date,
        offset: int,
        limit: int = PAGE_SIZE,
    ) -> tuple[list[Ga4Row], int]:
        days = (end_date - start_date).days + 1
        return [
            {
                "date": (start_date + timedelta(days=i)).strftime("%Y%m%d"),
                "pagePath": "/sync-fake/",
                "sessions": "20",
                "totalUsers": "15",
                "conversions": "2",
                "engagementRate": "0.7500",
            }
            for i in range(offset, min(offset + limit, days))
        ], days

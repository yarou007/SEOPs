"""Google Search Console transport and an explicit offline test implementation."""

import time
from datetime import date, timedelta
from pathlib import Path
from typing import Protocol, TypedDict
from urllib.parse import urlsplit

from google.oauth2 import service_account
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError

GSC_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
PAGE_SIZE = 25000


class GscRow(TypedDict):
    keys: list[str]
    clicks: float
    impressions: float
    ctr: float
    position: float


class GscQueryClient(Protocol):
    def query(
        self,
        site_property: str,
        start_date: date,
        end_date: date,
        start_row: int,
        row_limit: int = PAGE_SIZE,
    ) -> list[GscRow]: ...


class GscClient:
    def __init__(self, service_account_file: Path | None):
        self._service_account_file = service_account_file
        self._service: Resource | None = None

    def _get_service(self) -> Resource:
        # Load lazily: missing site properties and no-op runs need no credentials.
        if self._service is None:
            if self._service_account_file is None:
                raise ValueError("GSC_SERVICE_ACCOUNT_FILE is not set")
            try:
                credentials = service_account.Credentials.from_service_account_file(
                    str(self._service_account_file),
                    scopes=[GSC_SCOPE],
                )
            except Exception:
                # Credential parsers can expose input in exceptions. Never log that input.
                raise ValueError("Unable to load GSC service account file") from None
            try:
                self._service = build(
                    "searchconsole",
                    "v1",
                    credentials=credentials,
                    cache_discovery=False,
                    static_discovery=True,
                )
            except Exception:
                raise RuntimeError("Unable to initialize GSC API client") from None
        return self._service

    def query(
        self,
        site_property: str,
        start_date: date,
        end_date: date,
        start_row: int,
        row_limit: int = PAGE_SIZE,
    ) -> list[GscRow]:
        service = self._get_service()
        body = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "dimensions": ["date", "page", "query", "device"],
            "dataState": "final",
            "rowLimit": row_limit,
            "startRow": start_row,
        }
        for attempt in range(5):
            try:
                request = service.searchanalytics().query(siteUrl=site_property, body=body)
                response = request.execute(num_retries=0)
                return response.get("rows", [])
            except HttpError as exc:
                status = exc.resp.status
                if attempt == 4 or not (status == 429 or 500 <= status < 600):
                    raise
                time.sleep(2**attempt)
        raise AssertionError("unreachable")


class FakeGscClient:
    """Synthetic test-only rows, one per requested date; never reads credentials."""

    def query(
        self,
        site_property: str,
        start_date: date,
        end_date: date,
        start_row: int,
        row_limit: int = PAGE_SIZE,
    ) -> list[GscRow]:
        domain = (
            site_property.removeprefix("sc-domain:")
            if site_property.startswith("sc-domain:")
            else urlsplit(site_property).netloc
        )
        days = (end_date - start_date).days + 1
        return [
            {
                "keys": [
                    (start_date + timedelta(days=i)).isoformat(),
                    f"https://{domain}/sync-fake",
                    "TEST-ONLY synthetic query",
                    "mobile",
                ],
                "clicks": 3.0,
                "impressions": 20.0,
                "ctr": 0.15,
                "position": 2.25,
            }
            for i in range(start_row, min(start_row + row_limit, days))
        ]

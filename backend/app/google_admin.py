"""Setup helpers: list Google properties the service account can see, test saved properties.

Errors never expose exception text, file paths or credentials: callers get fixed messages.
"""

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build

from app.sync.ga4_client import Ga4Client
from app.sync.gsc_client import GSC_SCOPE, GscClient

logger = logging.getLogger(__name__)
GA4_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"
GSC_LIST_FAILED = (
    "Could not list Search Console properties. Check the service account and that the "
    "Search Console API is enabled. You can still type the property."
)
GA4_LIST_FAILED = (
    "Could not list GA4 properties. Check the service account and that the Google Analytics "
    "Admin API is enabled. You can still type the property ID."
)
GSC_TEST_FAILED = (
    "Search Console did not answer for this property. Check the property name and that the "
    "service account was added as a user."
)
GA4_TEST_FAILED = (
    "GA4 did not answer for this property. Check the property ID and that the service account "
    "has the Viewer role."
)


def _credentials(path: Path | None, scope: str):
    if path is None:
        raise ValueError("No service account file configured")
    return service_account.Credentials.from_service_account_file(str(path), scopes=[scope])


def _gsc_service(path: Path | None):
    return build(
        "searchconsole",
        "v1",
        credentials=_credentials(path, GSC_SCOPE),
        cache_discovery=False,
        static_discovery=True,
    )


def _ga4_admin_service(path: Path | None):
    return build(
        "analyticsadmin",
        "v1beta",
        credentials=_credentials(path, GA4_SCOPE),
        cache_discovery=False,
        static_discovery=True,
    )


def list_gsc_properties(path: Path | None) -> list[str]:
    response = _gsc_service(path).sites().list().execute(num_retries=0)
    return sorted(entry["siteUrl"] for entry in response.get("siteEntry", []))


def list_ga4_properties(path: Path | None) -> list[dict]:
    summaries = _ga4_admin_service(path).accountSummaries()
    properties, token = [], None
    for _ in range(50):  # at most 10,000 properties
        page = summaries.list(pageSize=200, pageToken=token).execute(num_retries=0)
        for account in page.get("accountSummaries", []):
            for item in account.get("propertySummaries", []):
                properties.append(
                    {
                        "id": item["property"].removeprefix("properties/"),
                        "name": item.get("displayName", ""),
                        "account": account.get("displayName", ""),
                    }
                )
        token = page.get("nextPageToken")
        if not token:
            break
    return sorted(properties, key=lambda item: (item["name"].lower(), item["id"]))


def options(gsc_path: Path | None, ga4_path: Path | None) -> dict:
    result = {}
    for source, lister, path, failed in [
        ("gsc", list_gsc_properties, gsc_path, GSC_LIST_FAILED),
        ("ga4", list_ga4_properties, ga4_path, GA4_LIST_FAILED),
    ]:
        try:
            result[source] = {"properties": lister(path), "error": None}
        except Exception:
            logger.warning("Listing %s properties failed", source)
            result[source] = {"properties": [], "error": failed}
    return result


def _window() -> tuple:
    end = datetime.now(UTC).date() - timedelta(days=3)
    return end - timedelta(days=6), end


def test_gsc(path: Path | None, site_property: str) -> tuple[bool, str]:
    start, end = _window()
    try:
        GscClient(path).query(site_property, start, end, 0, row_limit=1, dimensions=("date",))
    except Exception:
        logger.warning("GSC connection test failed")
        return False, GSC_TEST_FAILED
    return True, f"Search Console answered for {site_property}."


def test_ga4(path: Path | None, property_id: str) -> tuple[bool, str]:
    start, end = _window()
    try:
        Ga4Client(path).run_report(property_id, start, end, 0, limit=1)
    except Exception:
        logger.warning("GA4 connection test failed")
        return False, GA4_TEST_FAILED
    return True, f"GA4 answered for property {property_id}."

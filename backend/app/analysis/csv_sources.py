"""Bounded Ahrefs CSV ingestion. No external requests or spreadsheet evaluation."""

import csv
import io
import re
from collections import Counter
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from app.models import AxisSnapshot, Site


def domain(url: str) -> str:
    parsed = urlsplit(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username:
        raise ValueError("CSV URLs must be absolute HTTP or HTTPS URLs")
    return parsed.hostname.lower().removeprefix("www.").rstrip(".")


def _header(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower().lstrip("\ufeff"))


def import_csv(db: Session, site: Site, kind: str, text: str) -> AxisSnapshot:
    if len(text.encode("utf-8")) > 2_000_000:
        raise ValueError("CSV must be at most 2 MB")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",\t;")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    headers = {_header(key): key for key in (reader.fieldnames or [])}

    def column(*names):
        for name in names:
            if _header(name) in headers:
                return headers[_header(name)]
        raise ValueError("CSV is missing a required column: " + " / ".join(names))

    if kind == "internal-links":
        url_col = column("URL", "Page URL")
        inbound_col = column(
            "No. of inlinks", "Inlinks", "Incoming internal links", "Inbound links"
        )
        status_col = column("HTTP status code", "HTTP code", "Status code")
        orphan_col = next(
            (headers[name] for name in ["isorphan", "orphan"] if name in headers), None
        )
        pages = {}
        for index, row in enumerate(reader):
            if index >= 20_000:
                raise ValueError("CSV must contain at most 20,000 rows")
            url = (row.get(url_col) or "").strip()
            if domain(url) != site.domain.removeprefix("www."):
                raise ValueError("Site Audit URLs must belong to this website")
            try:
                inbound = int((row.get(inbound_col) or "").replace(",", ""))
                status = int(row.get(status_col) or "")
            except ValueError:
                raise ValueError("Inbound links and HTTP status must be integers") from None
            if inbound < 0 or not 100 <= status <= 599:
                raise ValueError("Invalid inbound count or HTTP status")
            orphan = (
                (row.get(orphan_col) or "").lower() in {"true", "yes", "1"}
                if orphan_col
                else inbound == 0 and urlsplit(url).path not in {"", "/"}
            )
            pages[url] = {
                "url": url,
                "inbound_links": inbound,
                "http_status": status,
                "orphan": orphan,
            }
        if not pages:
            raise ValueError("CSV has no page rows")
        distribution = Counter(row["inbound_links"] for row in pages.values())
        data = {
            "orphans": [row for row in pages.values() if row["orphan"]],
            "broken_links": [row for row in pages.values() if row["http_status"] >= 400],
            "inbound_distribution": [
                {"inbound_links": count, "pages": pages_count}
                for count, pages_count in sorted(distribution.items())
            ],
            "pages_count": len(pages),
            "note": (
                "Broken URLs are crawl targets with HTTP 4xx/5xx; "
                "Source-to-target edges require a link-level export. "
                "Zero inlinks is an orphan candidate, not proof of crawl completeness."
            ),
        }
    elif kind == "backlinks":
        source_col = column("Referring page URL", "Source URL")
        target_col = column("Target URL")
        links = set()
        for index, row in enumerate(reader):
            if index >= 20_000:
                raise ValueError("CSV must contain at most 20,000 rows")
            source, target = (
                (row.get(source_col) or "").strip(),
                (row.get(target_col) or "").strip(),
            )
            if domain(target) != site.domain.removeprefix("www."):
                raise ValueError("Backlink targets must belong to this website")
            links.add((source, target))
        if not links:
            raise ValueError("CSV has no backlink rows")
        data = {
            "links": [
                {
                    "source_domain": domain(source),
                    "target_domain": domain(target),
                    "source_url": source,
                    "target_url": target,
                }
                for source, target in sorted(links)
            ]
        }
    else:
        raise ValueError("Unknown CSV kind")
    evidence = AxisSnapshot(site=site.domain, kind=kind, data=data)
    db.add(evidence)
    db.flush()
    return evidence

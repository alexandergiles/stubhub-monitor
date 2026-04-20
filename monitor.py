"""Scrape a StubHub event page: total + per-level listing counts + price range."""

from __future__ import annotations

import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

EVENT_URL = "https://www.stubhub.com/phish-las-vegas-tickets-4-30-2026/event/159989155/"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
VIEWPORT = {"width": 1440, "height": 900}

DATA_CSV = Path(__file__).parent / "data.csv"

# Sphere ticket classes. Stable for this event's lifetime.
# Source: /index-data -> ticketClasses[*].{ticketClassId, name}
TICKET_CLASSES: list[tuple[int, str, str]] = [
    (3788, "100 Level", "100"),
    (3803, "200 Level", "200"),
    (17690, "300 Level", "300"),
    (8152, "400 Level", "400"),
    (682, "Floor", "floor"),
]

CSV_COLUMNS = [
    "timestamp_utc",
    "total_listings",
    *(f"count_{k}" for _, _, k in TICKET_CLASSES),
    "count_other",
    "min_price",
    "max_price",
    *(f"min_{k}" for _, _, k in TICKET_CLASSES),
    *(f"max_{k}" for _, _, k in TICKET_CLASSES),
    "available_tickets",
]

INDEX_DATA_RE = re.compile(
    r'<script id="index-data" type="application/json">(.+?)</script>',
    re.DOTALL,
)


def fetch_index_data(page, url: str) -> dict | None:
    """Navigate to url and return the parsed <script id="index-data"> JSON."""
    captured: dict[str, str] = {}

    def on_response(resp):
        if resp.url == url and "html" not in captured:
            try:
                captured["html"] = resp.text()
            except Exception as exc:
                print(f"warning: failed to read response body for {url}: {exc}", file=sys.stderr)

    page.on("response", on_response)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45_000)
    except Exception as exc:
        print(f"warning: goto failed for {url}: {exc}", file=sys.stderr)
        page.remove_listener("response", on_response)
        return None
    page.wait_for_timeout(1_500)
    page.remove_listener("response", on_response)

    html = captured.get("html")
    if not html:
        print(f"warning: no HTML captured for {url}", file=sys.stderr)
        return None
    m = INDEX_DATA_RE.search(html)
    if not m:
        print(f"warning: no index-data blob in {url}", file=sys.stderr)
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError as exc:
        print(f"warning: index-data JSON parse failed: {exc}", file=sys.stderr)
        return None


def price_range_from_histogram(data: dict) -> tuple[float | None, float | None]:
    h = data.get("histogram") or {}
    buckets = h.get("buckets") or []
    if not buckets:
        return None, None
    try:
        return float(buckets[0]["startPrice"]), float(buckets[-1]["endPrice"])
    except (KeyError, TypeError, ValueError):
        return None, None


def scrape() -> dict:
    row: dict = {c: None for c in CSV_COLUMNS}
    row["timestamp_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            ctx = browser.new_context(user_agent=USER_AGENT, viewport=VIEWPORT)
            page = ctx.new_page()

            base = fetch_index_data(page, EVENT_URL)
            if base:
                row["total_listings"] = base.get("totalListings")
                row["available_tickets"] = base.get("availableTickets")
                min_p, max_p = price_range_from_histogram(base)
                row["min_price"] = min_p
                row["max_price"] = max_p

            for tc_id, tc_name, key in TICKET_CLASSES:
                # quantity=0 → include listings of any size (single + pairs + groups)
                url = f"{EVENT_URL}?ticketClasses={tc_id}&quantity=0"
                d = fetch_index_data(page, url)
                if not d:
                    continue
                grid = d.get("grid") or {}
                count = grid.get("totalFilteredListings")
                if count is not None:
                    row[f"count_{key}"] = count
                else:
                    print(f"warning: no totalFilteredListings for {tc_name}", file=sys.stderr)
                # Per-class price range from visible items (sample of top 10 recommended)
                items = grid.get("items") or []
                prices = [i.get("rawPrice") for i in items if isinstance(i.get("rawPrice"), (int, float))]
                if prices:
                    row[f"min_{key}"] = round(min(prices), 2)
                    row[f"max_{key}"] = round(max(prices), 2)
        finally:
            browser.close()

    # Derive "other" bucket (Suites, zone tickets, etc. not in the 5 named levels).
    per_level_sum = sum(
        row[f"count_{key}"] for _, _, key in TICKET_CLASSES
        if isinstance(row[f"count_{key}"], int)
    )
    if isinstance(row["total_listings"], int):
        row["count_other"] = max(row["total_listings"] - per_level_sum, 0)

    return row


def append_row(row: dict) -> None:
    new_file = not DATA_CSV.exists()
    with DATA_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def main() -> int:
    try:
        row = scrape()
    except Exception as exc:
        print(f"warning: scrape failed: {exc}", file=sys.stderr)
        row = {c: None for c in CSV_COLUMNS}
        row["timestamp_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    append_row(row)
    per_level = " ".join(
        f"{name.split()[0]}={row[f'count_{key}']}(${row[f'min_{key}']}-${row[f'max_{key}']})"
        for _, name, key in TICKET_CLASSES
    )
    print(
        f"logged: total={row['total_listings']} {per_level} other={row['count_other']} "
        f"overall ${row['min_price']}-${row['max_price']} "
        f"at {row['timestamp_utc']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

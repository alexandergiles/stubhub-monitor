"""Scrape a StubHub event page and append the listing count + price range to data.csv."""

from __future__ import annotations

import csv
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
CSV_COLUMNS = ["timestamp_utc", "count", "min_price", "max_price", "raw_text"]

# "View 199 Listings" / "199 listings" / "Showing 10 of 199"
LISTINGS_COUNT_REGEX = re.compile(r"(\d{1,6})\s+listings?\b", re.IGNORECASE)
SHOWING_REGEX = re.compile(r"Showing\s+\d+\s+of\s+(\d{1,6})", re.IGNORECASE)
# Price range slider: "Price per ticket\n$100\n$791+"
PRICE_RANGE_REGEX = re.compile(
    r"Price per ticket\s*\$\s*([\d,]+)\s*\$\s*([\d,]+)",
    re.IGNORECASE,
)


def _to_int(s: str) -> int:
    return int(s.replace(",", ""))


def _to_float(s: str) -> float:
    return float(s.replace(",", ""))


def extract_listing_count(body_text: str) -> tuple[int | None, str]:
    m = SHOWING_REGEX.search(body_text)
    if m:
        return _to_int(m.group(1)), m.group(0)
    m = LISTINGS_COUNT_REGEX.search(body_text)
    if m:
        return _to_int(m.group(1)), m.group(0)
    return None, ""


def extract_price_range(body_text: str) -> tuple[float | None, float | None]:
    m = PRICE_RANGE_REGEX.search(body_text)
    if not m:
        return None, None
    try:
        return _to_float(m.group(1)), _to_float(m.group(2))
    except ValueError:
        return None, None


def scrape() -> dict:
    row = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": None,
        "min_price": None,
        "max_price": None,
        "raw_text": "",
    }

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            ctx = browser.new_context(user_agent=USER_AGENT, viewport=VIEWPORT)
            page = ctx.new_page()
            page.goto(EVENT_URL, wait_until="domcontentloaded", timeout=60_000)

            try:
                page.wait_for_load_state("load", timeout=30_000)
            except Exception as exc:
                print(f"warning: load state timeout: {exc}", file=sys.stderr)

            # Listings hydrate client-side; give them time and nudge with scrolls.
            page.wait_for_timeout(8_000)
            for y in (500, 1500, 2500):
                try:
                    page.evaluate(f"window.scrollTo(0, {y})")
                    page.wait_for_timeout(1_200)
                except Exception:
                    break
            page.wait_for_timeout(3_000)

            try:
                body_text = page.inner_text("body")
            except Exception as exc:
                print(f"warning: could not read body text: {exc}", file=sys.stderr)
                body_text = ""

            count, raw_text = extract_listing_count(body_text)
            row["count"] = count
            row["raw_text"] = raw_text

            min_price, max_price = extract_price_range(body_text)
            row["min_price"] = min_price
            row["max_price"] = max_price
        finally:
            browser.close()

    return row


def append_row(row: dict) -> None:
    new_file = not DATA_CSV.exists()
    with DATA_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def main() -> int:
    try:
        row = scrape()
    except Exception as exc:
        print(f"warning: scrape failed: {exc}", file=sys.stderr)
        row = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "count": None,
            "min_price": None,
            "max_price": None,
            "raw_text": f"error: {exc}",
        }
    append_row(row)
    print(
        f"logged: count={row['count']} "
        f"min=${row['min_price']} max=${row['max_price']} "
        f"at {row['timestamp_utc']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

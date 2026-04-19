"""Scrape a StubHub event page and append the listing count to data.csv."""

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
NEXT_DATA_DUMP = Path(__file__).parent / "last_next_data.json"
CSV_COLUMNS = ["timestamp_utc", "count", "min_price", "max_price", "raw_text"]

COUNT_REGEX = re.compile(r"(\d{1,5})\s+(ticket|listing)s?", re.IGNORECASE)
PRICE_REGEX = re.compile(r"\$\s*([\d,]+(?:\.\d{2})?)")


def extract_listing_count(body_text: str) -> tuple[int | None, str]:
    match = COUNT_REGEX.search(body_text)
    if not match:
        return None, ""
    return int(match.group(1)), match.group(0)


def extract_prices(page) -> tuple[float | None, float | None]:
    try:
        elements = page.query_selector_all('[data-testid*="price"], [class*="Price"]')
    except Exception as exc:
        print(f"warning: price selector failed: {exc}", file=sys.stderr)
        return None, None

    prices: list[float] = []
    for el in elements:
        try:
            text = el.inner_text()
        except Exception:
            continue
        for m in PRICE_REGEX.finditer(text):
            try:
                prices.append(float(m.group(1).replace(",", "")))
            except ValueError:
                continue

    if not prices:
        return None, None
    return min(prices), max(prices)


def dump_next_data(page) -> None:
    try:
        raw = page.evaluate(
            "() => {"
            "  const el = document.getElementById('__NEXT_DATA__');"
            "  return el ? el.textContent : null;"
            "}"
        )
    except Exception as exc:
        print(f"warning: __NEXT_DATA__ evaluate failed: {exc}", file=sys.stderr)
        return
    if not raw:
        print("warning: __NEXT_DATA__ not found on page", file=sys.stderr)
        return
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"warning: __NEXT_DATA__ is not valid JSON: {exc}", file=sys.stderr)
        NEXT_DATA_DUMP.write_text(raw, encoding="utf-8")
        return
    NEXT_DATA_DUMP.write_text(json.dumps(parsed, indent=2), encoding="utf-8")


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
            context = browser.new_context(user_agent=USER_AGENT, viewport=VIEWPORT)
            page = context.new_page()
            page.goto(EVENT_URL, wait_until="domcontentloaded", timeout=60_000)
            try:
                page.wait_for_load_state("networkidle", timeout=20_000)
            except Exception as exc:
                print(f"warning: networkidle not reached, continuing: {exc}", file=sys.stderr)

            try:
                body_text = page.inner_text("body")
            except Exception as exc:
                print(f"warning: could not read body text: {exc}", file=sys.stderr)
                body_text = ""

            count, raw_text = extract_listing_count(body_text)
            row["count"] = count
            row["raw_text"] = raw_text

            min_price, max_price = extract_prices(page)
            row["min_price"] = min_price
            row["max_price"] = max_price

            dump_next_data(page)
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

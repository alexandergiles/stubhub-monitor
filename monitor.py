"""Scrape a StubHub event page: total + per-level counts + true per-level price range.

Per-level prices: we click "Show more" on each class-filtered page until all listings are
loaded, then take min/max across ALL listings in that class. Takes ~60-90s per run.
"""

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
    "median_price",
    *(f"min_{k}" for _, _, k in TICKET_CLASSES),
    *(f"max_{k}" for _, _, k in TICKET_CLASSES),
    *(f"median_{k}" for _, _, k in TICKET_CLASSES),
    "available_tickets",
]

INDEX_DATA_RE = re.compile(
    r'<script id="index-data" type="application/json">(.+?)</script>',
    re.DOTALL,
)


def _median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return 0.0
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def parse_index_data(html: str) -> dict | None:
    m = INDEX_DATA_RE.search(html)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError as exc:
        print(f"warning: index-data parse failed: {exc}", file=sys.stderr)
        return None


def fetch_get(page, url: str) -> dict | None:
    """Navigate to url (GET) and parse the index-data blob."""
    captured: dict[str, str] = {}
    seen_urls: list[str] = []

    def on_response(resp):
        if resp.request.method != "GET":
            return
        seen_urls.append(resp.url)
        ct = resp.headers.get("content-type", "")
        if "text/html" in ct and "html" not in captured:
            try:
                body = resp.text()
                if INDEX_DATA_RE.search(body):
                    captured["html"] = body
            except Exception:
                pass

    page.on("response", on_response)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45_000)
    except Exception as exc:
        print(f"warning: goto {url}: {exc}", file=sys.stderr)
        page.remove_listener("response", on_response)
        return None
    page.wait_for_timeout(2_500)
    page.remove_listener("response", on_response)

    html = captured.get("html", "")
    if not html:
        print(f"warning: no index-data HTML for {url}", file=sys.stderr)
        print(f"  GET urls seen: {seen_urls[:5]}", file=sys.stderr)
        return None
    return parse_index_data(html)


def dismiss_modal(page) -> None:
    for sel in ['#modal-root button', '[aria-label*="Close" i]', 'button:has-text("Close")']:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0:
                loc.click(timeout=1_500)
                break
        except Exception:
            pass
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass


def collect_all_prices(page, url: str) -> tuple[int | None, list[float]]:
    """Load class-filtered URL, click Show More until exhausted, return (total, prices)."""
    prices: list[float] = []
    post_responses: list[str] = []
    html_holder: dict[str, str] = {}

    def on_response(resp):
        if resp.request.method == "GET" and "html" not in html_holder:
            ct = resp.headers.get("content-type", "")
            if "text/html" in ct:
                try:
                    body = resp.text()
                    if INDEX_DATA_RE.search(body):
                        html_holder["html"] = body
                except Exception:
                    pass
        if resp.request.method == "POST" and "phish-las-vegas" in resp.url:
            try:
                post_responses.append(resp.text())
            except Exception:
                pass

    page.on("response", on_response)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45_000)
    except Exception as exc:
        print(f"warning: goto {url}: {exc}", file=sys.stderr)
        page.remove_listener("response", on_response)
        return None, []
    page.wait_for_timeout(3_000)

    data = parse_index_data(html_holder.get("html") or "")
    if not data:
        page.remove_listener("response", on_response)
        return None, []
    grid = data.get("grid") or {}
    total = grid.get("totalFilteredListings")
    for item in grid.get("items") or []:
        rp = item.get("rawPrice")
        if isinstance(rp, (int, float)):
            prices.append(rp)

    if not total or total <= len(prices):
        page.remove_listener("response", on_response)
        return total, prices

    dismiss_modal(page)
    for y in (500, 1500, 2500, 3500):
        try:
            page.evaluate(f"window.scrollTo(0, {y})")
        except Exception:
            break
        page.wait_for_timeout(400)

    max_clicks = (total + 9) // 10 + 1  # small buffer
    for i in range(max_clicks):
        try:
            btn = page.locator('button:has-text("Show more")').first
            if btn.count() == 0:
                break
            btn.click(force=True, timeout=5_000)
            page.wait_for_timeout(1_100)
            page.evaluate("window.scrollBy(0, 1500)")
            page.wait_for_timeout(250)
        except Exception as exc:
            print(f"warning: show-more click {i+1}: {exc}", file=sys.stderr)
            break

    page.remove_listener("response", on_response)

    for rt in post_responses:
        try:
            d = json.loads(rt)
        except Exception:
            continue
        items = d.get("items") or d.get("grid", {}).get("items") or []
        for item in items:
            rp = item.get("rawPrice")
            if isinstance(rp, (int, float)):
                prices.append(rp)

    return total, prices


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

            base = fetch_get(page, EVENT_URL)
            if base:
                row["total_listings"] = base.get("totalListings")
                row["available_tickets"] = base.get("availableTickets")
                mn, mx = price_range_from_histogram(base)
                row["min_price"] = mn
                row["max_price"] = mx

            all_prices: list[float] = []
            for tc_id, tc_name, key in TICKET_CLASSES:
                url = f"{EVENT_URL}?ticketClasses={tc_id}&quantity=0"
                total, prices = collect_all_prices(page, url)
                if total is not None:
                    row[f"count_{key}"] = total
                if prices:
                    row[f"min_{key}"] = round(min(prices), 2)
                    row[f"max_{key}"] = round(max(prices), 2)
                    row[f"median_{key}"] = round(_median(prices), 2)
                    all_prices.extend(prices)
                    print(
                        f"  {tc_name}: {total} listings, "
                        f"captured {len(prices)} prices, "
                        f"${min(prices):.2f} - ${max(prices):.2f} (med ${_median(prices):.2f})",
                        file=sys.stderr,
                    )
            if all_prices:
                row["median_price"] = round(_median(all_prices), 2)
        finally:
            browser.close()

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

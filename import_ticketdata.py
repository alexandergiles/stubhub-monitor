"""One-off: import historical get-in prices from ticketdata.com and merge into data.csv.

Sources the same Phish @ Sphere event from data.ticketdata.com. Fills `min_price`
(from overall get_in_price) and `min_300`/`min_400` (from zone get_in prices) for
historical timestamps. Other columns left blank. Existing rows are preserved —
if a row already has a non-empty value in a column, it is NOT overwritten.
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

from monitor import CSV_COLUMNS

ROOT = Path(__file__).parent
DATA_CSV = ROOT / "data.csv"
EVENT_PAGE = "https://www.ticketdata.com/events/60937039"
API_URL = "https://data.ticketdata.com/api/events/60937039/price-history"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

# Zone name -> key used in our CSV column (e.g. min_{key}, median_{key}).
# ticketdata only exposes 300 Level and 400 Level for this event.
ZONE_TO_KEY = {
    "100 Level": "100",
    "200 Level": "200",
    "300 Level": "300",
    "400 Level": "400",
    "Floor": "floor",
}

# IANA timezones behind the abbreviations ticketdata uses.
TZ_OFFSETS = {
    "PST": -8,
    "PDT": -7,
    "UTC": 0,
}


def to_utc_iso(naive_local: str, tz_abbr: str) -> str | None:
    """Convert '2025-12-12T13:37:04' + 'PST' -> '2025-12-12T21:37:04+00:00'."""
    if tz_abbr not in TZ_OFFSETS:
        print(f"warning: unknown tz {tz_abbr}", file=sys.stderr)
        return None
    try:
        dt = datetime.fromisoformat(naive_local)
    except ValueError:
        return None
    utc_dt = dt - timedelta(hours=TZ_OFFSETS[tz_abbr])
    utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    return utc_dt.isoformat(timespec="seconds")


def fetch_history() -> dict:
    """Load the event page (to bypass Cloudflare), then fetch the API."""
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        ctx = b.new_context(user_agent=UA, viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        captured = {}

        def on_response(resp):
            if "price-history" in resp.url and "api" in resp.url:
                try:
                    captured["body"] = resp.text()
                except Exception:
                    pass

        page.on("response", on_response)
        page.goto(EVENT_PAGE, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(6_000)
        # Chart loads data lazily — scroll to it and click "All Time" to force fetch
        page.evaluate("window.scrollBy(0, 700)")
        page.wait_for_timeout(2_000)
        for label in ("All Time", "6 Months", "1 Month"):
            try:
                page.locator(f'button:has-text("{label}")').first.click(force=True, timeout=4_000)
                page.wait_for_timeout(2_500)
            except Exception:
                pass
        page.wait_for_timeout(2_000)
        b.close()

    body = captured.get("body")
    if not body:
        raise RuntimeError("ticketdata price-history API response not captured")
    return json.loads(body)["data"]


def build_historical_rows(payload: dict) -> dict[str, dict]:
    """Returns {timestamp_utc -> partial row dict with the columns we know}."""
    out: dict[str, dict] = {}

    # Overall get-in price
    for entry in payload.get("data", []):
        ts = to_utc_iso(entry["inserted_at"], entry.get("timezone") or "UTC")
        if not ts or ts < "2020":   # skip 1979 seed rows
            continue
        out.setdefault(ts, {})["min_price"] = entry["get_in_price"]

    # Per-zone get-in price
    for zone in payload.get("zones", []):
        key = ZONE_TO_KEY.get(zone.get("zone"))
        if not key:
            continue
        for entry in zone.get("data", []):
            ts = to_utc_iso(entry["inserted_at"], entry.get("timezone") or "UTC")
            if not ts or ts < "2020":
                continue
            out.setdefault(ts, {})[f"min_{key}"] = entry["zone_get_in_price"]

    return out


def main() -> int:
    payload = fetch_history()
    print(f"fetched: {payload.get('total_records')} overall, "
          f"{len(payload.get('zones', []))} zones")

    new_rows = build_historical_rows(payload)
    print(f"built {len(new_rows)} historical rows spanning "
          f"{min(new_rows)} → {max(new_rows)}")

    # Load existing data.csv, index by timestamp
    existing: dict[str, dict] = {}
    existing_header: list[str] = []
    if DATA_CSV.exists():
        with DATA_CSV.open() as f:
            reader = csv.DictReader(f)
            existing_header = reader.fieldnames or []
            for row in reader:
                existing[row["timestamp_utc"]] = row

    # Merge: for each historical row, if timestamp exists, fill only empty fields.
    # If it doesn't exist, create a new row.
    filled_count = 0
    added_count = 0
    for ts, partial in new_rows.items():
        if ts in existing:
            for k, v in partial.items():
                if not existing[ts].get(k):
                    existing[ts][k] = v
                    filled_count += 1
        else:
            row = {c: "" for c in CSV_COLUMNS}
            row["timestamp_utc"] = ts
            for k, v in partial.items():
                row[k] = v
            existing[ts] = row
            added_count += 1

    # Write back sorted by timestamp
    sorted_rows = sorted(existing.values(), key=lambda r: r["timestamp_utc"])
    with DATA_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in sorted_rows:
            writer.writerow(row)

    print(f"added {added_count} new rows, filled {filled_count} cells in existing rows")
    print(f"total rows now: {len(sorted_rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

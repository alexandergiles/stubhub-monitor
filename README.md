# StubHub Monitor

Tracks the number of tickets listed on StubHub for one hardcoded event and logs the counts to `data.csv` over time.

## What it does

Every time `monitor.py` runs, it:

1. Opens the event page in headless Chromium via Playwright.
2. Tries three extraction strategies in order — regex on the rendered body text, scanning price selectors for min/max, and dumping the `__NEXT_DATA__` JSON blob to `last_next_data.json` for future tuning.
3. Appends a row to `data.csv` with columns `timestamp_utc, count, min_price, max_price, raw_text`.

The event URL is hardcoded at the top of `monitor.py` (`EVENT_URL`). Edit it there to track a different show.

## Run locally

```bash
pip install -r requirements.txt
python -m playwright install chromium
python monitor.py
```

A new row will be appended to `data.csv` (the file is created with a header on the first run). `last_next_data.json` will also be written — inspect it to find a stable count field for the tuning step below.

## GitHub Action

`.github/workflows/monitor.yml` runs the scraper every 30 minutes via cron (`*/30 * * * *`) and on manual dispatch. It installs Playwright with `--with-deps` so the Ubuntu runner has the required system libraries, runs `monitor.py`, and commits any change to `data.csv` back to the repo using the `github-actions` bot identity.

If the first run fails to push, enable **Settings → Actions → General → Workflow permissions → Read and write permissions** on the repo.

## Tuning the extractor

The regex-based count is brittle — StubHub's DOM changes often. The stable fix is to read directly from the `__NEXT_DATA__` JSON that Next.js embeds in the page. `last_next_data.json` is that blob from the last run; grep it for fields like `totalListings`, `availableTickets`, or `ticketCount` and wire `monitor.py` to read the count straight from that JSON path.

## Note on StubHub ToS

StubHub's terms of service prohibit automated access. Keep the cadence reasonable, don't redistribute the data, and don't build a product on top of it. This is for personal curiosity only.

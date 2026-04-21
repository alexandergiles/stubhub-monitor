# StubHub Monitor

Tracks the number of tickets listed on StubHub for one hardcoded event and logs the counts to `data.csv` over time.

![Listings and price range over time](chart.png)

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
python monitor.py   # append a row to data.csv
python plot.py      # regenerate chart.png
```

## GitHub Action

`.github/workflows/monitor.yml` runs hourly via cron (`0 * * * *`) plus manual dispatch. It installs Playwright with `--with-deps`, runs `monitor.py`, regenerates `chart.png` with `plot.py`, and commits both back to the repo using the `github-actions` bot identity.

If the first run fails to push, enable **Settings → Actions → General → Workflow permissions → Read and write permissions** on the repo.

## How extraction works

StubHub server-renders an `<script id="index-data" type="application/json">` blob containing `totalListings`, `ticketClasses`, and `histogram` buckets. `monitor.py` parses that directly. For the per-level breakdown it loads the event URL 5 more times with `?ticketClasses=<id>&quantity=0` — each response's `grid.totalFilteredListings` gives the count for 100/200/300/400/Floor. `count_other` captures suites, zone tickets, and anything without an explicit level class.

If StubHub changes the embedded-data schema, the thing to retune is `fetch_index_data()` + the field paths in `scrape()`.

## Dashboard

Live dashboard: **https://alexandergiles.github.io/stubhub-monitor/** — hosted on GitHub Pages, auto-refreshes every 60 seconds, pulls directly from the committed `data.csv`.

To run locally instead:

```bash
python -m http.server 8765
# then open http://127.0.0.1:8765/
```

## Note on StubHub ToS

StubHub's terms of service prohibit automated access. Keep the cadence reasonable, don't redistribute the data, and don't build a product on top of it. This is for personal curiosity only.

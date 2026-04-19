# StubHub Monitor — Complete Build Instructions

A step-by-step guide to building a scheduled StubHub ticket-count tracker using Claude Code and GitHub Actions. No prior experience with either is assumed.

---

## What you'll end up with

- A Python script that opens your Phish event page in a headless browser, reads the listing count, and appends it to `data.csv`.
- A GitHub repository that runs that script automatically every 30 minutes and commits the results.
- A local copy on your machine you can run anytime with `python monitor.py`.

---

## Part 1 — One-time prerequisites

### 1.1 Install Claude Code

**Mac (recommended):** open Terminal and paste:

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

**Windows:** open PowerShell and paste:

```powershell
irm https://claude.ai/install.ps1 | iex
```

**Linux:** same curl command as Mac.

Close and reopen your terminal, then verify:

```bash
claude --version
```

You should see a version number. If you hit trouble, the official setup page is at https://code.claude.com/docs/en/setup.

### 1.2 Log in to Claude Code

Run `claude` in the terminal. It opens a browser window to authenticate. You need a paid Claude plan (Pro, Max, Team, or Enterprise) — the free tier does not include Claude Code.

### 1.3 Install Git (if you don't have it)

Check first:

```bash
git --version
```

If it prints a version, skip ahead. If not:

- **Mac:** run `xcode-select --install` and follow the prompts.
- **Windows:** download from https://git-scm.com/download/win and run the installer with defaults.
- **Linux:** `sudo apt install git` (Debian/Ubuntu) or equivalent.

### 1.4 Install the GitHub CLI (optional but makes the GitHub step trivial)

- **Mac:** `brew install gh`
- **Windows:** `winget install --id GitHub.cli`
- **Linux:** see https://github.com/cli/cli#installation

Then authenticate:

```bash
gh auth login
```

Pick GitHub.com → HTTPS → Login with a web browser, and follow the prompts. If you skip the CLI, you'll create the repo through github.com instead — I note both paths below.

### 1.5 Install Python 3.11 or newer

Check:

```bash
python3 --version
```

If it's missing or older than 3.11, install from https://www.python.org/downloads/ (Mac/Windows) or your package manager (Linux).

---

## Part 2 — Create the project folder

Pick somewhere you keep code projects. For example:

```bash
mkdir -p ~/projects/stubhub-monitor
cd ~/projects/stubhub-monitor
```

From here on, every command assumes you're in that directory.

---

## Part 3 — Launch Claude Code and build the project

Start Claude Code inside the folder:

```bash
claude
```

You'll see a prompt. **Paste the entire block below as a single message.** It tells Claude exactly what to build.

---

### THE PROMPT — copy everything between the lines

---

I'm building a small monitor that tracks how many tickets are listed on StubHub for one specific event over time, and logs the counts to a CSV. I want you to scaffold the whole project in this directory. Here's what I need:

**Project goal:** every time the script runs, open a hardcoded StubHub event page in a headless browser, extract the number of listings (and prices if easy), and append a row to `data.csv`. A GitHub Actions workflow should run it every 30 minutes and commit the CSV back to the repo.

**Hardcoded event URL:** `https://www.stubhub.com/phish-las-vegas-tickets-4-30-2026/event/159989155/`

**Create these files:**

1. `monitor.py` — the scraper. Use Playwright with Chromium in headless mode. Include a realistic user-agent and a 1440x900 viewport. Navigate to the event URL, wait for `networkidle`, then try three extraction strategies in order:
   - Regex the page body text for `(\d{1,5})\s+(ticket|listing)s?` to get the count.
   - Query `[data-testid*="price"], [class*="Price"]` elements, extract dollar amounts, and record min/max.
   - Read `document.getElementById('__NEXT_DATA__').textContent`, parse the JSON, and write it to `last_next_data.json` so I can inspect it and later wire up a direct lookup.
   
   Log a row to `data.csv` with columns `timestamp_utc, count, min_price, max_price, raw_text`. Create the file with a header on the first run. Wrap the Playwright call in try/except and print warnings to stderr so failures don't crash the GitHub Action.

2. `requirements.txt` — just `playwright>=1.40`.

3. `.github/workflows/monitor.yml` — a GitHub Actions workflow with a cron trigger `*/30 * * * *` plus `workflow_dispatch`. Steps: checkout with `actions/checkout@v4`, set up Python 3.11 with `actions/setup-python@v5`, `pip install -r requirements.txt`, `python -m playwright install --with-deps chromium`, run `python monitor.py`, then `git add data.csv` and commit/push any changes with a message like `update data <timestamp>`. Use `permissions: contents: write` and configure `github-actions` as the committer.

4. `.gitignore` — include `__pycache__/`, `*.pyc`, `.venv/`, `venv/`, `last_next_data.json`, and `.DS_Store`.

5. `README.md` — short explanation of what the project does, how to run it locally (`pip install -r requirements.txt`, `python -m playwright install chromium`, `python monitor.py`), how the GitHub Action works, a note that StubHub ToS may frown on scraping and to keep the cadence reasonable, and a note that the extractor will need occasional tuning when StubHub changes their DOM — pointing at `last_next_data.json` as the best way to find a stable count field.

**After creating the files:**

- Create a local Python venv at `.venv`, activate it, install the requirements, and install Chromium via `python -m playwright install chromium`.
- Run `python monitor.py` once to confirm it works end-to-end. If extraction returns `None` for the count, that's fine — the goal is to confirm Playwright launches, loads the page, and the CSV gets a row. Report what you see.
- Initialize a git repo, make an initial commit.

Tell me when you're done and summarize any warnings or issues you saw during the test run.

---

### END OF PROMPT

---

Claude Code will ask permission to create files, run `pip`, install Playwright, etc. Say yes. The whole build takes a few minutes, most of which is Playwright downloading Chromium.

When it's done, you should have a working project and a first row in `data.csv` (possibly with a `None` count — that's expected and we'll tune it next).

---

## Part 4 — Push to GitHub

### Option A: with the GitHub CLI (one command)

Still inside the project folder:

```bash
gh repo create stubhub-monitor --private --source=. --remote=origin --push
```

Done. Your repo is live and the code is pushed.

### Option B: without the CLI

1. Go to https://github.com/new, name the repo `stubhub-monitor`, leave it empty (no README, no .gitignore), and create it.
2. GitHub shows you a page with instructions. Copy the "push an existing repository" block, which looks like:
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/stubhub-monitor.git
   git branch -M main
   git push -u origin main
   ```
3. Paste those into your terminal.

---

## Part 5 — Turn on the scheduled Action

1. On github.com, open your repo → **Actions** tab.
2. If it asks you to enable workflows, click **I understand my workflows, go ahead and enable them**.
3. You should see the **StubHub monitor** workflow. Click it, then **Run workflow** → **Run workflow** to trigger a manual run immediately and confirm it works.
4. After ~1 minute it should finish green. Click into the run to see logs. When it's done, go to the **Code** tab and confirm `data.csv` has grown by one row.

From now on it runs every 30 minutes automatically.

### Allowing the Action to push commits

If the commit step fails with a permissions error on the first run, go to repo **Settings** → **Actions** → **General** → **Workflow permissions**, select **Read and write permissions**, and save. Re-run the workflow.

---

## Part 6 — Tune the extractor (the important part)

The regex-based count is fragile. The stable fix: open `last_next_data.json` (generated on the first local run) and find where StubHub actually stores the listing count.

Back in your project folder, launch Claude Code again:

```bash
claude
```

Paste this:

---

Open `last_next_data.json` and search for fields that look like they hold the total number of listings for this event — likely keys named something like `totalListings`, `availableTickets`, `ticketCount`, `totalTickets`, or similar. There may be several candidates; list the top 3–5 with their full JSON path and current value. Then update `monitor.py` so that the `__NEXT_DATA__` strategy in `extract_listing_count()` reads the count directly from that path and uses it as the primary source of truth, falling back to the regex only if the lookup fails. Run the script once to confirm it still works, then commit and push.

---

After this, your count will come from StubHub's own data blob rather than a fuzzy text match — much more reliable.

---

## Part 7 — Viewing the data later

A tiny plotting script you can drop into the project:

```python
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("data.csv", parse_dates=["timestamp_utc"])
df.plot(x="timestamp_utc", y="count", title="Listings over time")
plt.show()
```

Install with `pip install pandas matplotlib` inside the venv.

---

## Troubleshooting

**Playwright blocked by StubHub.** If after a few runs the count is consistently `None` and `last_next_data.json` looks stripped-down or like a challenge page, StubHub has flagged the runner. Options: drop the cadence to every 2–4 hours, run it locally on your own machine with cron/Task Scheduler instead of GitHub Actions, or route through a scraping service like ScrapingBee.

**GitHub Action fails to commit.** Almost always the workflow permissions issue in Part 5. Fix is one toggle in settings.

**Script works locally but not in the Action.** Check that `python -m playwright install --with-deps chromium` ran successfully in the Action logs — the `--with-deps` flag is what installs the system libraries Chromium needs on the Ubuntu runner.

**You want to track a different show later.** Edit the `EVENT_URL` constant at the top of `monitor.py`, commit, push.

---

## A reminder on terms of service

StubHub's ToS prohibit automated access. At personal-curiosity scale (one event, every 30 minutes, from one runner) you're very unlikely to cause anyone problems, but don't scale this up, don't redistribute the data, and don't build a product on top of it.

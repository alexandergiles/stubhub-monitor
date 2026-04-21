"""Render chart.png from data.csv with broken y-axis for listing counts."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).parent
DATA = ROOT / "data.csv"
OUT = ROOT / "chart.png"
EVENT_LABEL = "Phish · Sphere, Las Vegas · 2026-04-30"

LEVELS = [
    ("100", "100 Level", "#2563eb"),
    ("200", "200 Level", "#7c3aed"),
    ("300", "300 Level", "#db2777"),
    ("400", "400 Level", "#ea580c"),
    ("floor", "Floor", "#059669"),
]

TOP_YMIN, TOP_YMAX = 400, 750     # total + other land here
BOT_YMIN, BOT_YMAX = 0, 200        # per-level counts land here


def _plot_counts(ax_top, ax_bot, df):
    """Plot the same count series on both axes — they'll each show only their range."""
    for ax in (ax_top, ax_bot):
        ax.plot(
            df["timestamp_utc"], df["total_listings"],
            color="#0f172a", linewidth=2.4, marker="o", markersize=5, label="Total",
        )
        if "count_other" in df.columns and df["count_other"].notna().any():
            ax.plot(
                df["timestamp_utc"], df["count_other"],
                color="#94a3b8", linewidth=1.4, linestyle=":", marker="o", markersize=3, label="Other",
            )
        for key, label, color in LEVELS:
            col = f"count_{key}"
            if col in df.columns and df[col].notna().any():
                ax.plot(
                    df["timestamp_utc"], df[col],
                    color=color, linewidth=1.7, marker="o", markersize=3, label=label,
                )

    ax_top.set_ylim(TOP_YMIN, TOP_YMAX)
    ax_bot.set_ylim(BOT_YMIN, BOT_YMAX)

    # Hide the seam between the two axes
    ax_top.spines["bottom"].set_visible(False)
    ax_bot.spines["top"].set_visible(False)
    ax_top.tick_params(labelbottom=False, bottom=False)
    ax_top.xaxis.tick_top()

    # Diagonal break marks
    d = 0.008
    kw = dict(transform=ax_top.transAxes, color="k", clip_on=False, linewidth=1)
    ax_top.plot((-d, +d), (-d, +d), **kw)
    ax_top.plot((1 - d, 1 + d), (-d, +d), **kw)
    kw.update(transform=ax_bot.transAxes)
    h = (TOP_YMAX - TOP_YMIN) / (BOT_YMAX - BOT_YMIN)  # adjust break size per-axis height
    ax_bot.plot((-d, +d), (1 - d * h, 1 + d * h), **kw)
    ax_bot.plot((1 - d, 1 + d), (1 - d * h, 1 + d * h), **kw)

    for ax in (ax_top, ax_bot):
        ax.grid(True, linestyle=":", alpha=0.4)

    ax_top.legend(loc="upper left", framealpha=0.9, fontsize=9, ncol=4)


def _plot_prices(ax, df):
    for key, label, color in LEVELS:
        mn, mx = f"min_{key}", f"max_{key}"
        if mn in df.columns and mx in df.columns and df[mn].notna().any():
            ax.fill_between(
                df["timestamp_utc"], df[mn], df[mx],
                color=color, alpha=0.18, label=f"{label}",
            )
            ax.plot(df["timestamp_utc"], df[mn], color=color, linewidth=1.3, linestyle="--", alpha=0.9)
            ax.plot(df["timestamp_utc"], df[mx], color=color, linewidth=1.3, linestyle="--", alpha=0.9)

    if df["min_price"].notna().any():
        ax.plot(df["timestamp_utc"], df["min_price"], color="#0f172a", linewidth=1.3, marker="o", markersize=3, label="Overall min")
    if df["max_price"].notna().any():
        ax.plot(df["timestamp_utc"], df["max_price"], color="#475569", linewidth=1.3, marker="o", markersize=3, label="Overall max")

    ax.set_yscale("log")
    ax.set_ylabel("Price ($, log scale)")
    ax.grid(True, linestyle=":", alpha=0.4, which="both")
    ax.legend(loc="upper left", framealpha=0.9, fontsize=8, ncol=4)


def main() -> int:
    if not DATA.exists():
        print(f"no data at {DATA}", file=sys.stderr)
        return 1

    df = pd.read_csv(DATA, parse_dates=["timestamp_utc"])
    df = df.dropna(subset=["total_listings"]).sort_values("timestamp_utc")
    if df.empty:
        print("no valid rows to plot", file=sys.stderr)
        return 1

    fig = plt.figure(figsize=(13, 11))
    gs = fig.add_gridspec(3, 1, height_ratios=[0.75, 1.15, 1.3], hspace=0.1)
    ax_count_top = fig.add_subplot(gs[0])
    ax_count_bot = fig.add_subplot(gs[1], sharex=ax_count_top)
    ax_price = fig.add_subplot(gs[2], sharex=ax_count_top)
    # Shrink hspace between the two count panels to make the break feel like one chart
    gs.update(hspace=0.3)
    pos_top = ax_count_top.get_position()
    pos_bot = ax_count_bot.get_position()
    ax_count_top.set_position([pos_top.x0, pos_bot.y1 + 0.01, pos_top.width, pos_top.height])

    _plot_counts(ax_count_top, ax_count_bot, df)
    ax_count_bot.set_ylabel("Listings")
    ax_count_top.set_title(
        f"Listings over time — latest {int(df.iloc[-1]['total_listings'])} total (broken y-axis)",
        fontsize=11, pad=8,
    )

    _plot_prices(ax_price, df)
    latest = df.iloc[-1]
    if pd.notna(latest.get("min_price")) and pd.notna(latest.get("max_price")):
        ax_price.set_title(
            f"Per-level price range — overall ${latest['min_price']:.0f}-${latest['max_price']:.0f}",
            fontsize=11, pad=8,
        )

    ax_price.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    if len(df) < 3:
        center = df["timestamp_utc"].iloc[-1]
        ax_price.set_xlim(center - pd.Timedelta(hours=6), center + pd.Timedelta(hours=6))
    for label in ax_price.get_xticklabels():
        label.set_rotation(30)
        label.set_ha("right")

    fig.suptitle(
        f"{EVENT_LABEL}  ·  {latest['timestamp_utc']:%Y-%m-%d %H:%M UTC}",
        fontsize=13, fontweight="bold", y=0.995,
    )
    fig.savefig(OUT, dpi=120, bbox_inches="tight")
    print(f"wrote {OUT} ({len(df)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

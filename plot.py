"""Render chart.png from data.csv: listing count + price range over time."""

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


def main() -> int:
    if not DATA.exists():
        print(f"no data at {DATA}", file=sys.stderr)
        return 1

    df = pd.read_csv(DATA, parse_dates=["timestamp_utc"])
    df = df.dropna(subset=["count"]).sort_values("timestamp_utc")

    if df.empty:
        print("no valid rows to plot", file=sys.stderr)
        return 1

    fig, ax_count = plt.subplots(figsize=(11, 5.5))
    ax_price = ax_count.twinx()

    ax_count.plot(
        df["timestamp_utc"], df["count"],
        color="#2563eb", linewidth=2, marker="o", markersize=4,
        label="Listings",
    )
    ax_count.set_ylabel("Listings", color="#2563eb")
    ax_count.tick_params(axis="y", labelcolor="#2563eb")
    ax_count.grid(True, linestyle=":", alpha=0.4)

    has_prices = df["min_price"].notna().any() and df["max_price"].notna().any()
    if has_prices:
        ax_price.fill_between(
            df["timestamp_utc"], df["min_price"], df["max_price"],
            color="#f97316", alpha=0.15, label="Price range",
        )
        ax_price.plot(
            df["timestamp_utc"], df["min_price"],
            color="#f97316", linewidth=1.2, linestyle="--", label="Min $",
        )
        ax_price.plot(
            df["timestamp_utc"], df["max_price"],
            color="#c2410c", linewidth=1.2, linestyle="--", label="Max $",
        )
        ax_price.set_ylabel("Price ($)", color="#c2410c")
        ax_price.tick_params(axis="y", labelcolor="#c2410c")

    ax_count.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    if len(df) < 3:
        center = df["timestamp_utc"].iloc[-1]
        ax_count.set_xlim(center - pd.Timedelta(hours=6), center + pd.Timedelta(hours=6))
    fig.autofmt_xdate()

    latest = df.iloc[-1]
    subtitle = (
        f"Latest: {int(latest['count'])} listings"
        + (
            f" · ${latest['min_price']:.0f}–${latest['max_price']:.0f}"
            if pd.notna(latest.get("min_price")) and pd.notna(latest.get("max_price"))
            else ""
        )
        + f" · {latest['timestamp_utc']:%Y-%m-%d %H:%M UTC}"
    )
    fig.suptitle(EVENT_LABEL, fontsize=13, fontweight="bold", y=0.98)
    ax_count.set_title(subtitle, fontsize=10, color="#444", pad=10)

    lines_count, labels_count = ax_count.get_legend_handles_labels()
    lines_price, labels_price = ax_price.get_legend_handles_labels()
    if lines_count or lines_price:
        ax_count.legend(
            lines_count + lines_price,
            labels_count + labels_price,
            loc="upper left",
            framealpha=0.9,
            fontsize=9,
        )

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(OUT, dpi=120, bbox_inches="tight")
    print(f"wrote {OUT} ({len(df)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Render chart.png from data.csv: total + per-level listings + price range over time."""

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
    ("count_100", "100 Level", "#2563eb"),
    ("count_200", "200 Level", "#7c3aed"),
    ("count_300", "300 Level", "#db2777"),
    ("count_400", "400 Level", "#ea580c"),
    ("count_floor", "Floor", "#059669"),
    ("count_other", "Other", "#64748b"),
]


def main() -> int:
    if not DATA.exists():
        print(f"no data at {DATA}", file=sys.stderr)
        return 1

    df = pd.read_csv(DATA, parse_dates=["timestamp_utc"])
    df = df.dropna(subset=["total_listings"]).sort_values("timestamp_utc")
    if df.empty:
        print("no valid rows to plot", file=sys.stderr)
        return 1

    fig, (ax_top, ax_bot) = plt.subplots(
        2, 1, figsize=(11, 8), sharex=True,
        gridspec_kw={"height_ratios": [1.4, 1]},
    )

    # Top: total + per-level lines
    ax_top.plot(
        df["timestamp_utc"], df["total_listings"],
        color="#0f172a", linewidth=2.4, marker="o", markersize=5, label="Total",
    )
    for col, label, color in LEVELS:
        if col not in df.columns or df[col].isna().all():
            continue
        ax_top.plot(
            df["timestamp_utc"], df[col],
            color=color, linewidth=1.6, marker="o", markersize=3, label=label,
        )
    ax_top.set_ylabel("Listings")
    ax_top.grid(True, linestyle=":", alpha=0.4)
    ax_top.legend(loc="upper left", framealpha=0.9, fontsize=9, ncol=3)
    ax_top.set_title(
        f"Listings over time — latest {int(df.iloc[-1]['total_listings'])} total",
        fontsize=11, pad=8,
    )

    # Bottom: price range band
    has_prices = df["min_price"].notna().any() and df["max_price"].notna().any()
    if has_prices:
        ax_bot.fill_between(
            df["timestamp_utc"], df["min_price"], df["max_price"],
            color="#f97316", alpha=0.2, label="Price range",
        )
        ax_bot.plot(df["timestamp_utc"], df["min_price"],
                    color="#ea580c", linewidth=1.4, linestyle="--", label="Min")
        ax_bot.plot(df["timestamp_utc"], df["max_price"],
                    color="#c2410c", linewidth=1.4, linestyle="--", label="Max")
    ax_bot.set_ylabel("Price ($)")
    ax_bot.grid(True, linestyle=":", alpha=0.4)
    ax_bot.legend(loc="upper left", framealpha=0.9, fontsize=9)
    latest = df.iloc[-1]
    if pd.notna(latest.get("min_price")) and pd.notna(latest.get("max_price")):
        ax_bot.set_title(
            f"Price range — latest ${latest['min_price']:.0f}–${latest['max_price']:.0f}",
            fontsize=11, pad=8,
        )

    ax_bot.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    if len(df) < 3:
        center = df["timestamp_utc"].iloc[-1]
        ax_bot.set_xlim(center - pd.Timedelta(hours=6), center + pd.Timedelta(hours=6))
    fig.autofmt_xdate()

    fig.suptitle(
        f"{EVENT_LABEL}  ·  {latest['timestamp_utc']:%Y-%m-%d %H:%M UTC}",
        fontsize=13, fontweight="bold", y=0.995,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(OUT, dpi=120, bbox_inches="tight")
    print(f"wrote {OUT} ({len(df)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

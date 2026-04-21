"""Render chart.png: listings and prices over time, both log-scale."""

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


def main() -> int:
    if not DATA.exists():
        print(f"no data at {DATA}", file=sys.stderr)
        return 1

    df = pd.read_csv(DATA, parse_dates=["timestamp_utc"])
    df = df.dropna(subset=["total_listings"]).sort_values("timestamp_utc")
    if df.empty:
        print("no valid rows to plot", file=sys.stderr)
        return 1

    fig, (ax_count, ax_price) = plt.subplots(
        2, 1, figsize=(12, 9), sharex=True,
    )

    # Counts: log scale
    ax_count.plot(
        df["timestamp_utc"], df["total_listings"],
        color="#0f172a", linewidth=2.4, marker="o", markersize=5, label="Total",
    )
    if "count_other" in df.columns and df["count_other"].notna().any():
        ax_count.plot(
            df["timestamp_utc"], df["count_other"],
            color="#94a3b8", linewidth=1.4, linestyle=":", marker="o", markersize=3, label="Other",
        )
    for key, label, color in LEVELS:
        col = f"count_{key}"
        if col in df.columns and df[col].notna().any():
            ax_count.plot(
                df["timestamp_utc"], df[col],
                color=color, linewidth=1.7, marker="o", markersize=3, label=label,
            )
    ax_count.set_yscale("log")
    ax_count.set_ylabel("Listings (log scale)")
    ax_count.grid(True, linestyle=":", alpha=0.4, which="both")
    ax_count.legend(loc="upper left", framealpha=0.9, fontsize=9, ncol=4)
    latest = df.iloc[-1]
    ax_count.set_title(
        f"Listings over time — latest {int(latest['total_listings'])} total",
        fontsize=11, pad=8,
    )

    # Prices: log scale
    for key, label, color in LEVELS:
        mn, mx = f"min_{key}", f"max_{key}"
        if mn in df.columns and mx in df.columns and df[mn].notna().any():
            ax_price.fill_between(
                df["timestamp_utc"], df[mn], df[mx],
                color=color, alpha=0.18, label=label,
            )
            ax_price.plot(df["timestamp_utc"], df[mn], color=color, linewidth=1.3, linestyle="--", alpha=0.9)
            ax_price.plot(df["timestamp_utc"], df[mx], color=color, linewidth=1.3, linestyle="--", alpha=0.9)
    if df["min_price"].notna().any():
        ax_price.plot(df["timestamp_utc"], df["min_price"], color="#0f172a", linewidth=1.3, marker="o", markersize=3, label="Overall min")
    if df["max_price"].notna().any():
        ax_price.plot(df["timestamp_utc"], df["max_price"], color="#475569", linewidth=1.3, marker="o", markersize=3, label="Overall max")
    ax_price.set_yscale("log")
    ax_price.set_ylabel("Price ($, log scale)")
    ax_price.grid(True, linestyle=":", alpha=0.4, which="both")
    ax_price.legend(loc="upper left", framealpha=0.9, fontsize=8, ncol=4)
    if pd.notna(latest.get("min_price")) and pd.notna(latest.get("max_price")):
        ax_price.set_title(
            f"Per-level price range — overall ${latest['min_price']:.0f}-${latest['max_price']:.0f}",
            fontsize=11, pad=8,
        )

    ax_price.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    if len(df) < 3:
        center = df["timestamp_utc"].iloc[-1]
        ax_price.set_xlim(center - pd.Timedelta(hours=6), center + pd.Timedelta(hours=6))
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

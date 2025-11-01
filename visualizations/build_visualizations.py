#!/usr/bin/env python3
"""
Build static plots and an animated choropleth for the ECDC COVID dataset.

Examples
--------
python build_visualizations.py \
    --input ../data/encounters.ndjson \
    --output-dir outputs \
    --frames-dir frames \
    --video covid_cases.mp4

Dependencies
------------
pip install pandas seaborn matplotlib plotly kaleido imageio geopandas (optional for future work)
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt
from matplotlib import dates as mdates
from matplotlib.colors import Normalize

try:
    import plotly.express as px  # type: ignore
    import plotly.io as pio  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    px = None
    pio = None

try:
    from matplotlib import animation as mpl_animation
except ImportError:  # pragma: no cover
    mpl_animation = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to encounters.ndjson")
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Directory where static figures will be saved (PNG format)",
    )
    parser.add_argument(
        "--frames-dir",
        default="frames",
        help="Directory to store animation frames before video assembly",
    )
    parser.add_argument(
        "--video",
        default="covid_animation.mp4",
        help="Filename for the generated video (mp4). Set to empty string to skip.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=15,
        help="Number of countries to display in the bar chart",
    )
    return parser.parse_args()


def load_dataset(path: str) -> pd.DataFrame:
    df = pd.read_json(path, lines=True)
    df["date"] = pd.to_datetime(df["dateRep"], format="%d/%m/%Y")
    df["cases"] = pd.to_numeric(df["cases"], errors="coerce").fillna(0).astype(int)
    df["deaths"] = pd.to_numeric(df["deaths"], errors="coerce").fillna(0).astype(int)
    df["popData2019"] = pd.to_numeric(df["popData2019"], errors="coerce")
    df["month_label"] = df["date"].dt.to_period("M").astype(str)
    df["month_start"] = df["date"].dt.to_period("M").dt.to_timestamp()
    return df


def compute_aggregates(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    top_countries = (
        df.groupby("countriesAndTerritories", as_index=False)
        .agg(
            total_cases=("cases", "sum"),
            total_deaths=("deaths", "sum"),
            population=("popData2019", "max"),
            continent=("continentExp", "last"),
        )
    )
    top_countries["case_fatality_rate"] = (
        (top_countries["total_deaths"] / top_countries["total_cases"])
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0)
        * 100
    )
    top_countries["cases_per_100k"] = (
        (top_countries["total_cases"] / top_countries["population"])
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0)
        * 100000
    )
    top_countries = top_countries.sort_values("total_cases", ascending=False)

    continent_monthly = (
        df.groupby(["month_start", "month_label", "continentExp"], as_index=False)
        .agg(cases=("cases", "sum"))
        .sort_values(["month_start", "continentExp"])
    )

    monthly_trend = (
        df.groupby(["year", "month"], as_index=False)
        .agg(cases=("cases", "sum"), deaths=("deaths", "sum"))
        .sort_values(["year", "month"])
    )
    monthly_trend["label"] = monthly_trend["year"].astype(str) + "-" + monthly_trend["month"].astype(str).str.zfill(2)

    df_sorted = df.sort_values("date")
    rolling = (
        df_sorted.groupby("countriesAndTerritories")
        .apply(lambda group: group.set_index("date")["cases"].rolling("14D", closed="right").sum().max())
        .reset_index(name="peakRolling14")
        .sort_values("peakRolling14", ascending=False)
    )
    return top_countries, continent_monthly, monthly_trend, rolling


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def plot_top_countries(df: pd.DataFrame, top_n: int, output: Path):
    sns.set_theme(style="whitegrid")
    subset = df.head(top_n).copy()
    subset = subset.sort_values("total_cases")
    fig, ax = plt.subplots(figsize=(12, 6))
    cmap = plt.cm.magma
    norm = Normalize(
        vmin=subset["case_fatality_rate"].min(),
        vmax=subset["case_fatality_rate"].max(),
    )
    colors = cmap(norm(subset["case_fatality_rate"].to_numpy()))
    bars = ax.barh(
        subset["countriesAndTerritories"],
        subset["total_cases"],
        color=colors,
    )
    ax.set_title(f"Top {top_n} Countries by Reported COVID-19 Cases (2020)")
    ax.set_xlabel("Total cases")
    ax.set_ylabel("")
    for bar, cfr in zip(bars, subset["case_fatality_rate"]):
        ax.text(
            bar.get_width() * 1.01,
            bar.get_y() + bar.get_height() / 2,
            f"{cfr:.2f}%",
            va="center",
            fontsize=9,
            color="black",
        )
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    fig.colorbar(sm, ax=ax, label="Case fatality rate (%)")
    plt.tight_layout()
    fig.savefig(output, dpi=300)
    plt.close(fig)


def plot_continent_area(df: pd.DataFrame, output: Path):
    pivot = (
        df.pivot_table(index="month_start", columns="continentExp", values="cases", fill_value=0)
        .sort_index()
    )
    x = mdates.date2num(pivot.index.to_pydatetime())
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.stackplot(x, pivot.values.T, labels=pivot.columns)
    ax.set_title("Monthly Cases by Continent (2019–2020)")
    ax.set_ylabel("Cases")
    ax.legend(loc="upper left")
    ax.xaxis_date()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    fig.tight_layout()
    fig.savefig(output, dpi=300)
    plt.close(fig)


def plot_monthly_trend(df: pd.DataFrame, output: Path):
    fig, ax_cases = plt.subplots(figsize=(12, 6))
    indexes = np.arange(len(df))

    bar = ax_cases.bar(indexes, df["cases"], color="#5088ff", alpha=0.7, label="Cases (left axis)")
    ax_cases.set_ylabel("Cases")
    ax_cases.set_xlabel("Month")
    ax_cases.set_title("Monthly Global Cases and Deaths (dual axis)")

    ax_deaths = ax_cases.twinx()
    line = ax_deaths.plot(
        indexes,
        df["deaths"],
        color="#d62728",
        marker="o",
        linewidth=2,
        label="Deaths (right axis)",
    )[0]
    ax_deaths.set_ylabel("Deaths")

    ax_cases.set_xticks(indexes)
    ax_cases.set_xticklabels(df["label"], rotation=45, ha="right")

    handles = [bar, line]
    labels = [h.get_label() for h in handles]
    ax_cases.legend(handles, labels, loc="upper left")

    fig.tight_layout()
    fig.savefig(output, dpi=300)
    plt.close(fig)


def plot_peak_heatmap(df: pd.DataFrame, output: Path):
    top = df.head(30).copy()
    plt.figure(figsize=(10, 8))
    sns.heatmap(
        top.set_index("countriesAndTerritories"),
        annot=True,
        fmt=".0f",
        cmap="magma",
        cbar_kws={"label": "Peak 14-day rolling cases"},
    )
    plt.title("Top 30 Peak 14-day Rolling Incidence")
    plt.tight_layout()
    plt.savefig(output, dpi=300)
    plt.close()


def build_animation(df: pd.DataFrame, frames_dir: Path, video_path: Path):
    if px is None or pio is None or mpl_animation is None:
        print("Plotly or matplotlib animation not available; skipping animation.")
        return
    ensure_dir(frames_dir)
    monthly = (
        df.groupby(["month_label", "countryterritoryCode"], as_index=False)
        .agg(total_cases=("cases", "sum"))
    )
    scale_max = monthly["total_cases"].max()
    unique_months = sorted(monthly["month_label"].unique())
    for idx, month in enumerate(unique_months):
        frame_df = monthly[monthly["month_label"] == month]
        fig = px.choropleth(
            frame_df,
            locations="countryterritoryCode",
            color="total_cases",
            color_continuous_scale="Viridis",
            range_color=(0, scale_max),
            title=f"COVID-19 Monthly Cases - {month}",
        )
        fig.update_layout(coloraxis_colorbar=dict(title="Cases"))
        frame_path = frames_dir / f"frame_{idx:03d}.png"
        pio.write_image(fig, str(frame_path), format="png", width=1200, height=600, engine="kaleido")
        print(f"Saved animation frame {frame_path}")

    if video_path:
        import matplotlib.pyplot as plt  # local import to avoid backend issues
        fig, ax = plt.subplots(figsize=(10, 5))
        plt.axis('off')

        def update(frame_index):
            ax.clear()
            ax.axis('off')
            img = plt.imread(frames_dir / f"frame_{frame_index:03d}.png")
            ax.imshow(img)

        ani = mpl_animation.FuncAnimation(
            fig,
            update,
            frames=len(unique_months),
            interval=250,
            repeat=False,
        )
        ani.save(video_path, writer="ffmpeg")
        plt.close(fig)


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    frames_dir = Path(args.frames_dir)
    ensure_dir(output_dir)

    df = load_dataset(args.input)
    top_countries, continent_monthly, monthly_trend, rolling = compute_aggregates(df)

    plot_top_countries(top_countries, args.top_n, output_dir / "top_countries.png")
    plot_continent_area(continent_monthly, output_dir / "continent_area.png")
    plot_monthly_trend(monthly_trend, output_dir / "monthly_trend.png")
    plot_peak_heatmap(rolling, output_dir / "peak14_heatmap.png")

    if args.video and px is not None and mpl_animation is not None:
        ensure_dir(frames_dir)
        build_animation(df, frames_dir, Path(args.video))

    print(f"Saved static plots to {output_dir.resolve()}")
    if args.video and px is not None and mpl_animation is not None:
        print(f"Video written to {Path(args.video).resolve()}")
    elif args.video:
        print("Install plotly and matplotlib with animation support to enable video export (skipped).")


if __name__ == "__main__":
    main()

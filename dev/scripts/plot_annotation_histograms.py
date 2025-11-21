#!/usr/bin/env python3
"""
Plot per-source histograms for annotated scores and export a means table.

Generates, for each distinct 'source':
  - Histogram for annotated_utility_score with dashed mean line and label
  - Histogram for annotated_feasibility_score with dashed mean line and label
  - A CSV table summarizing means per source for both scores

Unannotated rows are dropped per-metric (only scored rows are included).

Usage:
  python -m dev.scripts.plot_annotation_histograms \
    --csv /absolute/path/to/combined_for_annotation.csv \
    --outdir /absolute/path/to/annotation_plots
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

try:
    import pandas as pd
except Exception as e:  # pragma: no cover
    raise SystemExit("pandas is required. Install with: pip install pandas") from e
try:
    import matplotlib.pyplot as plt
    import seaborn as sns
except Exception as e:  # pragma: no cover
    raise SystemExit("matplotlib and seaborn are required. Install with: pip install matplotlib seaborn") from e


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Per-source histograms and means for annotated scores.")
    p.add_argument("--csv", required=True, help="Input CSV with columns: source, annotated_utility_score, annotated_feasibility_score.")
    p.add_argument("--outdir", required=True, help="Directory to write plots and summary CSV.")
    p.add_argument("--dpi", type=int, default=160, help="Image DPI (default: 160).")
    return p.parse_args()


def _ensure_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _discrete_bins_1_to_5() -> List[float]:
    # Bin edges centered on 1..5 integers: (0.5, 1.5, ..., 5.5)
    return [x + 0.5 for x in range(0, 6)]


def plot_histogram(values: pd.Series, title: str, mean_value: float, out_path: Path, dpi: int) -> None:
    plt.figure(figsize=(6, 4))
    sns.set(style="whitegrid")
    bins = _discrete_bins_1_to_5()
    # Use seaborn histplot; works well for discrete scores
    sns.histplot(values, bins=bins, kde=False, edgecolor="black", color="#60a5fa")
    plt.axvline(mean_value, color="black", linestyle="--", linewidth=1.5, label=f"Mean = {mean_value:.2f}")
    # Place mean text near line (top-right corner or above line)
    ymax = plt.gca().get_ylim()[1]
    plt.text(mean_value + 0.05, 0.92 * ymax, f"Mean = {mean_value:.2f}", rotation=90, va="top", ha="left", fontsize=9, color="black")
    plt.title(title)
    plt.xlabel("Score (1–5)")
    plt.ylabel("Count")
    plt.xlim(0.5, 5.5)
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=dpi)
    plt.close()


def main() -> None:
    args = parse_args()
    csv_path = Path(args.csv).expanduser().resolve()
    outdir = Path(args.outdir).expanduser().resolve()

    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")
    outdir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path)
    if "source" not in df.columns:
        raise SystemExit("CSV must include a 'source' column.")

    # Convert to numeric; keep NaN for unannotated rows
    if "annotated_utility_score" not in df.columns:
        df["annotated_utility_score"] = pd.NA
    if "annotated_feasibility_score" not in df.columns:
        df["annotated_feasibility_score"] = pd.NA
    df["annotated_utility_score"] = _ensure_numeric(df["annotated_utility_score"])
    df["annotated_feasibility_score"] = _ensure_numeric(df["annotated_feasibility_score"])

    # Compute means per source (dropping NaN per metric)
    utility_means = (df.dropna(subset=["annotated_utility_score"])
                       .groupby("source")["annotated_utility_score"]
                       .mean())
    feasibility_means = (df.dropna(subset=["annotated_feasibility_score"])
                           .groupby("source")["annotated_feasibility_score"]
                           .mean())
    summary = pd.concat([utility_means, feasibility_means], axis=1).rename(
        columns={
            "annotated_utility_score": "mean_annotated_utility_score",
            "annotated_feasibility_score": "mean_annotated_feasibility_score",
        }
    )
    summary_path = outdir / "means_by_source.csv"
    summary.to_csv(summary_path, index=True)

    # Per-source histograms
    for source_value, g in df.groupby("source"):
        # Utility
        util_vals = g["annotated_utility_score"].dropna()
        if len(util_vals) > 0:
            util_mean = float(util_vals.mean())
            util_title = f"{source_value} — annotated_utility_score"
            util_out = outdir / f"{source_value}_utility_hist.png"
            plot_histogram(util_vals, util_title, util_mean, util_out, dpi=args.dpi)

        # Feasibility
        feas_vals = g["annotated_feasibility_score"].dropna()
        if len(feas_vals) > 0:
            feas_mean = float(feas_vals.mean())
            feas_title = f"{source_value} — annotated_feasibility_score"
            feas_out = outdir / f"{source_value}_feasibility_hist.png"
            plot_histogram(feas_vals, feas_title, feas_mean, feas_out, dpi=args.dpi)

    print(f"Wrote per-source histograms and summary table to {outdir}")
    print(f"Means table: {summary_path}")


if __name__ == "__main__":
    main()



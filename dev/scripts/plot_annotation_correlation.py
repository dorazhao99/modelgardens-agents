#!/usr/bin/env python3
"""
Scatter plots comparing annotated scores vs original scores, with Pearson r and r^2.

Pairs:
- annotated_utility_score (1–5)   vs value_score (typically 1–10 in data)
- annotated_feasibility_score     vs feasibility_score

Only rows with both numbers present are included per pair.

Usage:
  python -m dev.scripts.plot_annotation_correlation \
    --csv /absolute/path/to/combined_for_annotation.csv \
    --outdir /absolute/path/to/annotation_plots
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Tuple

try:
    import numpy as np
    import pandas as pd
except Exception as e:  # pragma: no cover
    raise SystemExit("pandas and numpy are required. Install with: pip install pandas numpy") from e
try:
    import matplotlib.pyplot as plt
    import seaborn as sns
except Exception as e:  # pragma: no cover
    raise SystemExit("matplotlib and seaborn are required. Install with: pip install matplotlib seaborn") from e


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Plot correlation between annotated and original scores.")
    p.add_argument("--csv", required=True, help="Input CSV path.")
    p.add_argument("--outdir", required=True, help="Output directory for plots.")
    p.add_argument("--dpi", type=int, default=160, help="Plot DPI (default: 160).")
    return p.parse_args()


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _pearson(x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
    """
    Return (r, r_squared). Both x and y must be 1D numeric arrays of equal length.
    """
    if x.size == 0 or y.size == 0:
        return float("nan"), float("nan")
    r = float(np.corrcoef(x, y)[0, 1])
    return r, r * r


def _scatter_with_stats(x: pd.Series, y: pd.Series, x_label: str, y_label: str, title: str, out_path: Path, dpi: int) -> None:
    x_vals = _to_numeric(x).to_numpy(dtype=float)
    y_vals = _to_numeric(y).to_numpy(dtype=float)
    mask = np.isfinite(x_vals) & np.isfinite(y_vals)
    x_vals = x_vals[mask]
    y_vals = y_vals[mask]

    if x_vals.size == 0:
        print(f"[warn] No overlapping annotated/original data for {title}; skipping.")
        return

    r, r2 = _pearson(x_vals, y_vals)

    plt.figure(figsize=(6, 5))
    sns.set(style="whitegrid")
    ax = sns.scatterplot(x=x_vals, y=y_vals, s=30, color="#2563eb", edgecolor="white", linewidth=0.5)

    # Best-fit line (simple least-squares)
    try:
        coeffs = np.polyfit(x_vals, y_vals, deg=1)
        xs = np.linspace(x_vals.min(), x_vals.max(), 100)
        ys = coeffs[0] * xs + coeffs[1]
        plt.plot(xs, ys, color="#0f172a", linestyle="-", linewidth=1.5, label="OLS fit")
    except Exception:
        pass

    # Annotate statistics
    text = f"Pearson r = {r:.3f}\nr² = {r2:.3f}\nN = {x_vals.size}"
    x_min, x_max = float(np.nanmin(x_vals)), float(np.nanmax(x_vals))
    y_min, y_max = float(np.nanmin(y_vals)), float(np.nanmax(y_vals))
    x_pos = x_min + 0.03 * (x_max - x_min if x_max > x_min else 1.0)
    y_pos = y_max - 0.05 * (y_max - y_min if y_max > y_min else 1.0)
    plt.text(x_pos, y_pos, text, ha="left", va="top", fontsize=10, bbox=dict(facecolor="white", alpha=0.8, edgecolor="#ddd"))

    plt.title(title)
    plt.xlabel(x_label)
    plt.ylabel(y_label)
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

    # Column presence checks
    for col in ["annotated_utility_score", "annotated_feasibility_score", "value_score", "feasibility_score"]:
        if col not in df.columns:
            # Create empty column if missing to simplify filtering (will drop as NaN later)
            df[col] = pd.NA

    # Utility vs value_score
    _scatter_with_stats(
        x=df["annotated_utility_score"],
        y=df["value_score"],
        x_label="Annotated Utility (1–5)",
        y_label="Original Value Score",
        title="Annotated Utility vs Original Value",
        out_path=outdir / "correlation_annotated_utility_vs_value.png",
        dpi=args.dpi,
    )

    # Feasibility vs feasibility_score
    _scatter_with_stats(
        x=df["annotated_feasibility_score"],
        y=df["feasibility_score"],
        x_label="Annotated Feasibility (1–5)",
        y_label="Original Feasibility Score",
        title="Annotated Feasibility vs Original Feasibility",
        out_path=outdir / "correlation_annotated_feasibility_vs_feasibility.png",
        dpi=args.dpi,
    )

    print(f"Correlation plots written to: {outdir}")


if __name__ == "__main__":
    main()



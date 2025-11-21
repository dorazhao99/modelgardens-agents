#!/usr/bin/env python3
"""
Drop all rows where project or project_name matches a given string (default: 'Cotomata').

Usage:
  In-place overwrite:
    python -m dev.scripts.filter_drop_project --csv /absolute/path/to/combined_for_annotation.csv

  Write to a new file:
    python -m dev.scripts.filter_drop_project --csv /abs/in.csv --output /abs/out.csv --project "Cotomata"
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List, Tuple


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Drop rows by project/project_name and save CSV.")
    p.add_argument("--csv", required=True, help="Input CSV path to filter.")
    p.add_argument("--output", help="Optional output CSV path. If omitted, overwrites input.")
    p.add_argument("--project", default="Cotomata", help="Project name to drop (default: Cotomata).")
    return p.parse_args()


def read_csv(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        headers = [h for h in (reader.fieldnames or []) if h is not None]
        rows = [dict(r) for r in reader]
    return headers, rows


def write_csv(path: Path, headers: List[str], rows: List[Dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def should_drop(row: Dict[str, str], target: str) -> bool:
    target_norm = (target or "").strip().lower()
    proj = (row.get("project") or "").strip().lower()
    pname = (row.get("project_name") or "").strip().lower()
    return proj == target_norm or pname == target_norm


def main() -> None:
    args = parse_args()
    in_path = Path(args.csv).expanduser().resolve()
    out_path = Path(args.output).expanduser().resolve() if args.output else in_path

    if not in_path.exists():
        raise SystemExit(f"Input CSV not found: {in_path}")

    headers, rows = read_csv(in_path)
    before = len(rows)
    filtered = [r for r in rows if not should_drop(r, args.project)]
    write_csv(out_path, headers, filtered)
    print(f"Dropped {before - len(filtered)} rows matching project '{args.project}'. Wrote {len(filtered)} rows to {out_path}")


if __name__ == "__main__":
    main()



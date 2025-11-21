#!/usr/bin/env python3
"""
Concatenate heterogeneous CSVs for annotation.

- Accepts any number of input CSV files
- Unions all columns across inputs (missing values become empty)
- Adds a 'source' column indicating the origin (basename of file)
- Adds an empty 'annotated_utility_score' column for annotators
- Shuffles the resulting rows

Usage:
  python -m dev.scripts.concat_for_annotation \
    --output dev/survey/data_collection/11_20_experiments/combined_for_annotation.csv \
    /path/to/default_next_steps.csv \
    /path/to/full_pipeline.csv \
    /path/to/no_history.csv \
    /path/to/no_user.csv

Convenience:
  If no input files are provided, the script will attempt to load the four
  default CSVs from this repository under:
    dev/survey/data_collection/11_20_experiments/
"""
from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Concatenate CSVs for annotation with source and annotated_utility_score columns, shuffled.")
    parser.add_argument(
        "inputs",
        nargs="*",
        help="Input CSV file paths. If omitted, defaults to the 4 known CSVs under dev/survey/data_collection/11_20_experiments/.",
    )
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Path to write the combined CSV.",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=None,
        help="Optional random seed for deterministic shuffling.",
    )
    return parser.parse_args()


def default_input_paths(repo_root: Path) -> List[Path]:
    base = repo_root / "dev" / "survey" / "data_collection" / "11_20_experiments"
    candidates = [
        base / "default_next_steps.csv",
        base / "full_pipeline.csv",
        base / "no_history.csv",
        base / "no_user.csv",
    ]
    return [p for p in candidates if p.exists()]


def read_csv_with_source(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    """
    Returns header (fieldnames) and rows (list of dicts) for the given CSV.
    """
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = [dict(r) for r in reader]
        # Normalize None keys if any (defensive)
        fieldnames = [fn for fn in (reader.fieldnames or []) if fn is not None]
    # Append source indicator for each row
    source_value = path.stem  # basename without extension
    for r in rows:
        r["source"] = source_value
        # Harmonize message/task_description: prefer existing task_description, else fallback to message
        # Do not mutate original keys beyond harmonization; actual column removal handled later.
        td = r.get("task_description", "")
        msg = r.get("message", "")
        if (td is None or str(td).strip() == "") and (msg is not None and str(msg).strip() != ""):
            r["task_description"] = msg
    return fieldnames, rows


def union_headers(headers_list: Iterable[List[str]]) -> List[str]:
    """
    Compute a stable union of headers in the order first-seen across inputs.
    """
    seen: Set[str] = set()
    ordered: List[str] = []
    for headers in headers_list:
        for h in headers:
            if h not in seen:
                seen.add(h)
                ordered.append(h)
    return ordered


def main() -> None:
    args = parse_args()

    # Determine repo root: this file is dev/scripts/concat_for_annotation.py
    repo_root = Path(__file__).resolve().parents[2]

    input_paths: List[Path]
    if args.inputs:
        input_paths = [Path(p).expanduser().resolve() for p in args.inputs]
    else:
        input_paths = default_input_paths(repo_root)
        if not input_paths:
            raise SystemExit("No inputs provided and no defaults found. Please pass input CSV paths.")

    # Read all inputs and collect rows
    per_file_headers: List[List[str]] = []
    all_rows: List[Dict[str, str]] = []
    for p in input_paths:
        if not p.exists():
            raise FileNotFoundError(f"Input not found: {p}")
        headers, rows = read_csv_with_source(p)
        per_file_headers.append(headers + ["source"])  # ensure source is considered in union
        all_rows.extend(rows)

    # Build headers from actual row keys to capture harmonized fields
    seen_keys: List[str] = []
    seen_set: Set[str] = set()
    for r in all_rows:
        for k in r.keys():
            if k not in seen_set:
                seen_set.add(k)
                seen_keys.append(k)

    headers_union = list(seen_keys)

    # Drop the original 'message' column from output; keep canonical 'task_description'
    if "message" in headers_union:
        headers_union = [h for h in headers_union if h != "message"]
    if "task_description" not in headers_union:
        headers_union.insert(0, "task_description")  # ensure it exists; position not critical

    # Ensure annotated_utility_score at the end
    if "annotated_utility_score" not in headers_union:
        headers_union.append("annotated_utility_score")

    # Ensure each row contains all headers; fill missing with empty string
    for r in all_rows:
        # Remove 'message' from rows to avoid duplicate content in output
        if "message" in r:
            r.pop("message", None)
        # Ensure canonical field exists
        if "task_description" not in r:
            r["task_description"] = ""
        if "annotated_utility_score" not in r:
            r["annotated_utility_score"] = ""
        for h in headers_union:
            if h not in r:
                r[h] = ""

    # Shuffle rows
    rng = random.Random(args.random_seed)
    rng.shuffle(all_rows)

    # Write output
    out_path = Path(args.output).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers_union)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"Wrote {len(all_rows)} rows to {out_path}")


if __name__ == "__main__":
    main()



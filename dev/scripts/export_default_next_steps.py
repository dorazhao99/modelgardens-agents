#!/usr/bin/env python3
"""
Export the first N "Next Steps" entries for each project into a CSV file.

Default output: dev/default_next_steps.csv

Columns:
- project_name
- index (0-based within "Next Steps" for that project, by created_at ASC)
- message
- confidence
- entry_id
- created_at
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Dict, Iterable, List

# Ensure repository src/ is importable when running from the repo
THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[2]  # .../background-agents
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from precursor.scratchpad import store  # type: ignore  # noqa: E402


def list_projects_from_db() -> List[str]:
    store.init_db()
    conn = store.get_conn()
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT project_name
            FROM scratchpad_entries
            WHERE status = 'active'
            ORDER BY project_name ASC
            """
        ).fetchall()
        return [r["project_name"] for r in rows]
    finally:
        conn.close()


def collect_next_steps(project_name: str, limit: int) -> List[Dict]:
    # store.list_entries returns rows ordered by created_at ASC
    rows = store.list_entries(project_name, section="Next Steps")
    return rows[:limit]


def write_csv(rows: Iterable[Dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["project_name", "index", "message", "confidence", "entry_id", "created_at"])
        for r in rows:
            writer.writerow(
                [
                    r.get("project_name", ""),
                    r.get("_index", 0),
                    r.get("message", ""),
                    r.get("confidence", 0),
                    r.get("id", ""),
                    r.get("created_at", ""),
                ]
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Export the first N "Next Steps" entries per project into a CSV.'
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=30,
        help="Number of Next Steps to export per project (default: 30)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(REPO_ROOT / "dev" / "default_next_steps.csv"),
        help="Output CSV path (default: dev/default_next_steps.csv)",
    )
    parser.add_argument(
        "--projects",
        type=str,
        nargs="*",
        help="Optional list of project names to include (default: detect from DB)",
    )
    args = parser.parse_args()

    projects = args.projects if args.projects else list_projects_from_db()
    output_path = Path(args.output)

    aggregated: List[Dict] = []
    for project in projects:
        next_steps = collect_next_steps(project, limit=args.limit)
        for idx, row in enumerate(next_steps):
            row_copy = dict(row)
            row_copy["_index"] = idx  # local index within Next Steps for this project
            aggregated.append(row_copy)

    write_csv(aggregated, output_path)
    print(f"Wrote {len(aggregated)} rows to {output_path}")


if __name__ == "__main__":
    main()



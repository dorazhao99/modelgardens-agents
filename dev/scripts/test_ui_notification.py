#!/usr/bin/env python3
from __future__ import annotations

import logging
import sys
from pathlib import Path


def _ensure_src_on_path() -> None:
    """
    Allow running this script directly from the repo without installing the package.
    """
    repo_root = Path(__file__).resolve().parents[2]
    src_dir = repo_root / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    _ensure_src_on_path()

    from precursor.managers.ui_manager import UIManager

    project_name = "Personalization Dataset Collection"
    print(f"Triggering UI notification for project: {project_name}")
    manager = UIManager()
    result = manager.run_for_project(project_name)
    print("UIManager.run_for_project returned:")
    print(result)


if __name__ == "__main__":
    main()



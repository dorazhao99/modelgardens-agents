"""
Fast folder search core tool.

Use this when you specifically need to find a directory by name.
It is generally FASTER and more targeted than filesystem.search_files for folder lookups.

Backends (auto-detected per-OS) with hard timeouts:
- macOS: Spotlight (mdfind), fd, find
- Linux: locate/plocate, fd, find
- Windows: Everything, fd, PowerShell
- Optional Python walker fallback in a separate process with strict limits
"""

from __future__ import annotations

from typing import List, Optional

from precursor.mcp_servers.coder.fast_find import find_folders


def search_folders_fast(
    folder_name: str,
    root: Optional[str] = None,
    timeout: Optional[float] = None,
) -> List[str]:
    """
    Search for directories by name using fast, OS-native backends with strict timeouts.

    Recommended over `filesystem.search_files` when your goal is to locate a specific folder/repo.

    Parameters
    ----------
    folder_name : str
        Directory name to find (e.g., "my-repo" or "background-agents").
    root : str, optional
        Optional search root to constrain the search (e.g., "~/Documents").
    timeout : float, optional
        Global wall-clock time budget (seconds) for the entire search.

    Returns
    -------
    List[str]
        Absolute paths to matching directories (strings).
    """
    paths = find_folders(
        name=folder_name,
        root=root,
        require_git=False,
        max_results=25,
        prefer="auto",
        timeout=timeout,
        backend_timeout=5.0,
        allow_slow_python_fallback=True,
        python_max_depth=12,
        python_max_dirs_scanned=200_000,
    )
    return [str(p) for p in paths]



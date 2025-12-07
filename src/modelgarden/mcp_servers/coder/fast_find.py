#!/usr/bin/env python3
"""
fast_find.py — Cross-platform fast folder search with smart fallbacks and hard timeouts.

Import:
    from fast_find import find_folders
    hits = find_folders("autometrics-site", timeout=5.0)

CLI:
    python fast_find.py --name autometrics-site --timeout 5
"""

from __future__ import annotations
import argparse
import os
import platform
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from typing import Iterable, Optional, List
from concurrent.futures import ProcessPoolExecutor, TimeoutError as FUTimeout

# -------- Config --------
PRUNE_DIR_NAMES = {".git", ".svn", ".hg", ".venv", "node_modules", "__pycache__", "Library"}
PRUNE_PATH_SUBSTRINGS = {
    "/System/Volumes/Data/private/var/",
    "/private/var/",
    "/Volumes/Time Machine/",
}
if platform.system() == "Windows":
    PRUNE_PATH_SUBSTRINGS |= {
        "\\Windows\\WinSxS\\", "\\Windows\\System32\\", "\\ProgramData\\",
        "\\AppData\\Local\\Packages\\", "\\$Recycle.Bin\\",
    }

# -------- Helpers --------
def _which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)

def _run(cmd: str | list[str], timeout: float = 10.0) -> list[str]:
    """Run a subprocess with a hard timeout (preemptible)."""
    try:
        args = shlex.split(cmd) if isinstance(cmd, str) else cmd
        out = subprocess.check_output(
            args, text=True, stderr=subprocess.DEVNULL, timeout=timeout
        )
        return [line.strip() for line in out.splitlines() if line.strip()]
    except Exception:
        return []

def _is_git_repo(path: Path) -> bool:
    try:
        return (path / ".git").exists()
    except Exception:
        return False

def _dedup_keep_order(items: Iterable[str]) -> list[str]:
    seen, out = set(), []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out

# -------- Backends (subprocess) --------
def _spotlight_search(name: str, root: Optional[str], timeout: float) -> list[str]:
    if platform.system() != "Darwin" or not _which("mdfind"):
        return []
    exact_q = f'kMDItemFSName == "{name}" && kMDItemContentTypeTree == "public.folder"'
    res = _run(["mdfind", exact_q], timeout=timeout)
    if not res and root:
        res = _run(["mdfind", "-onlyin", str(Path(root).expanduser().resolve()), name], timeout=timeout)
    if not res:
        res = _run(["mdfind", name], timeout=timeout)
    return res

def _locate_search(name: str, _root: Optional[str], timeout: float) -> list[str]:
    if platform.system() != "Linux":
        return []
    locate = _which("plocate") or _which("locate")
    if not locate:
        return []
    return _run([locate, "-r", rf"/{name}$"], timeout=timeout)

def _everything_search(name: str, root: Optional[str], timeout: float) -> list[str]:
    if platform.system() != "Windows" or not _which("es.exe"):
        return []
    args = ["es.exe", "-name", name, "-attributes", "D"]
    if root:
        args += ["-path", str(Path(root).expanduser().resolve())]
    return _run(args, timeout=timeout)

def _fd_search(name: str, root: Optional[str], timeout: float) -> list[str]:
    if not _which("fd"):
        return []
    root_path = str(Path(root).expanduser().resolve()) if root else (
        "/" if platform.system() != "Windows" else "C:\\"
    )
    return _run(["fd", "-t", "d", "-H", "-a", name, root_path], timeout=timeout)

def _find_search_posix(name: str, root: Optional[str], timeout: float) -> list[str]:
    if platform.system() == "Windows":
        return []
    root_path = str(Path(root).expanduser().resolve()) if root else "/"
    prune_parts = []
    for n in PRUNE_DIR_NAMES:
        prune_parts += ["-name", n, "-o"]
    for p in PRUNE_PATH_SUBSTRINGS:
        prune_parts += ["-path", p, "-o"]
    prune_expr = "\\( " + " ".join(prune_parts[:-1]) + " \\) -prune -o" if prune_parts else ""
    cmd = f'find {shlex.quote(root_path)} {prune_expr} -type d -name {shlex.quote(name)} -print'
    return _run(["bash", "-lc", cmd], timeout=timeout)

def _powershell_search(name: str, root: Optional[str], timeout: float) -> list[str]:
    if platform.system() != "Windows" or not _which("powershell"):
        return []
    root_path = str(Path(root).expanduser().resolve()) if root else "C:\\"
    ps = (
        f"Get-ChildItem -Directory -Recurse -ErrorAction SilentlyContinue "
        f"-LiteralPath '{root_path}' | Where-Object {{$_.Name -eq '{name}'}} | "
        f"Select-Object -ExpandProperty FullName"
    )
    return _run(["powershell", "-NoProfile", "-Command", ps], timeout=timeout)

# -------- Python walker (run in a separate process) --------
def _python_walk_worker(
    name: str,
    root: Optional[str],
    max_results: int,
    max_depth: int,
    max_dirs_scanned: int,
    wall_time_limit: float,
) -> list[str]:
    """Runs in a separate process; cooperatively stops on budgets."""
    start = time.time()
    roots: list[Path]
    if root:
        roots = [Path(root).expanduser().resolve()]
    else:
        if platform.system() == "Windows":
            roots = [Path(f"{d}:\\") for d in "CDEFGHIJKLMNOPQRSTUVWXYZ" if Path(f"{d}:\\").exists()] or [Path("C:\\")]
        else:
            roots = [Path("/")]
    hits: list[str] = []
    scanned = 0

    def depth_of(p: Path, base: Path) -> int:
        try:
            return len(p.relative_to(base).parts)
        except Exception:
            return 0

    for base in roots:
        for dirpath, dirnames, _ in os.walk(base, topdown=True, followlinks=False):
            now = time.time()
            if wall_time_limit and (now - start) > wall_time_limit:
                return hits
            scanned += 1
            if scanned >= max_dirs_scanned:
                return hits

            p = Path(dirpath)
            # Depth pruning
            if max_depth >= 0 and depth_of(p, base) > max_depth:
                dirnames[:] = []
                continue
            # Path-based pruning
            ps = str(p)
            if any(s in ps for s in PRUNE_PATH_SUBSTRINGS):
                dirnames[:] = []
                continue
            # Dirname pruning
            dirnames[:] = [d for d in dirnames if d not in PRUNE_DIR_NAMES]

            # Match
            if name in dirnames:
                candidate = p / name
                try:
                    if candidate.is_dir():
                        hits.append(str(candidate))
                except Exception:
                    pass
                if len(hits) >= max_results:
                    return hits
    return hits

def _python_walk_safe(
    name: str,
    root: Optional[str],
    max_results: int,
    backend_timeout: float,
    max_depth: int,
    max_dirs_scanned: int,
) -> list[str]:
    """Run python walk in a subprocess with a hard timeout; kill if it exceeds budget."""
    with ProcessPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(
            _python_walk_worker,
            name, root, max_results, max_depth, max_dirs_scanned, backend_timeout
        )
        try:
            return fut.result(timeout=backend_timeout + 0.5)  # small guard
        except FUTimeout:
            # Hard kill the worker process
            fut.cancel()
            return []

# -------- Public API --------
def find_folders(
    name: str,
    root: Optional[str] = None,
    require_git: bool = False,
    max_results: int = 25,
    prefer: str = "auto",
    timeout: Optional[float] = None,         # total wall-clock budget (None = unlimited)
    backend_timeout: float = 5.0,            # per-backend hard timeout (sec)
    allow_slow_python_fallback: bool = True, # include python walker as last resort
    python_max_depth: int = 12,              # bound depth to avoid pathological trees
    python_max_dirs_scanned: int = 200_000,  # safety cap on directories scanned
) -> list[Path]:
    """
    Find directories named `name` across the system with hard timeouts.

    - All external tools run with subprocess timeouts.
    - The Python walker runs in a *separate process* and is killed if it exceeds `backend_timeout`.
    - A global `timeout` caps total wall-clock time for the whole search.
    """
    system = platform.system()
    if prefer != "auto":
        backends = [prefer]
    else:
        if system == "Darwin":
            backends = ["spotlight", "fd", "find"]
        elif system == "Linux":
            backends = ["locate", "fd", "find"]
        else:
            backends = ["everything", "fd", "powershell"]
        if allow_slow_python_fallback:
            backends.append("python")

    deadline = time.time() + timeout if timeout else None
    hits: list[str] = []

    for be in backends:
        # Stop if global deadline expired
        if deadline and time.time() > deadline:
            break

        # Compute remaining per-backend budget respecting global deadline
        be_budget = backend_timeout
        if deadline:
            remain = max(0.0, deadline - time.time())
            be_budget = min(be_budget, remain)
            if be_budget <= 0:
                break

        if be == "spotlight":
            hits = _spotlight_search(name, root, be_budget)
        elif be == "locate":
            hits = _locate_search(name, root, be_budget)
        elif be == "everything":
            hits = _everything_search(name, root, be_budget)
        elif be == "fd":
            hits = _fd_search(name, root, be_budget)
        elif be == "find":
            hits = _find_search_posix(name, root, be_budget)
        elif be == "powershell":
            hits = _powershell_search(name, root, be_budget)
        elif be == "python":
            hits = _python_walk_safe(
                name=name,
                root=root,
                max_results=max_results,
                backend_timeout=be_budget,
                max_depth=python_max_depth,
                max_dirs_scanned=python_max_dirs_scanned,
            )
        else:
            hits = []

        hits = _dedup_keep_order(hits)
        if require_git:
            hits = [h for h in hits if _is_git_repo(Path(h))]
        if hits:
            if len(hits) > max_results > 0:
                hits = hits[:max_results]
            return [Path(h) for h in hits]

    return []

# -------- CLI --------
def _cli() -> None:
    ap = argparse.ArgumentParser(description="Fast cross-platform folder finder with hard timeouts.")
    ap.add_argument("--name", required=True, help="Folder name to find (e.g., autometrics-site)")
    ap.add_argument("--root", default=None, help="Optional root directory to limit the search (e.g., ~)")
    ap.add_argument("--git", action="store_true", help="Only report matches that are Git repos")
    ap.add_argument("--max", type=int, default=25, help="Limit the number of results")
    ap.add_argument("--prefer", default="auto",
                    choices=["auto","spotlight","locate","everything","fd","find","powershell","python"],
                    help="Force a specific backend (debugging)")
    ap.add_argument("--timeout", type=float, default=None, help="Global timeout in seconds (e.g., 5)")
    ap.add_argument("--backend-timeout", type=float, default=5.0, help="Per-backend timeout seconds")
    ap.add_argument("--no-python", action="store_true", help="Disable slow python fallback")
    ap.add_argument("--py-max-depth", type=int, default=12, help="Depth bound for python walker")
    ap.add_argument("--py-max-dirs", type=int, default=200_000, help="Dir scan cap for python walker")
    args = ap.parse_args()

    results = find_folders(
        name=args.name,
        root=args.root,
        require_git=args.git,
        max_results=args.max,
        prefer=args.prefer,
        timeout=args.timeout,
        backend_timeout=args.backend_timeout,
        allow_slow_python_fallback=not args.no_python,
        python_max_depth=args.py_max_depth,
        python_max_dirs_scanned=args.py_max_dirs,
    )

    if results:
        print(f"\nFound {len(results)} result(s):")
        for p in results:
            print(p)
    else:
        print("\nNo matches found (or timed out).")

if __name__ == "__main__":
    _cli()
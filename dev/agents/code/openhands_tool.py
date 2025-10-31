# openhands_tool.py
import os
import asyncio
import json
import hashlib
import argparse
from pathlib import Path
from typing import Optional, Any

from platformdirs import user_data_dir
from openhands.events.action import MessageAction
from openhands.core.main import run_controller, auto_continue_response
from openhands.core.config import setup_config_from_args

# ------------------------
# Helpers
# ------------------------

def _make_traj_path(
    project_name: str,
    task: str,
    *,
    appauthor: Optional[str] = None
) -> Path:
    """Compute a trajectory path under a platform-appropriate user dir.
    Filename includes a short hash of the task description for uniqueness."""
    base_dir = Path(user_data_dir(appname="precursor", appauthor=appauthor, version=None))
    proj_dir = base_dir / project_name
    traj_dir = proj_dir / "trajectories"
    traj_dir.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256(task.encode("utf-8")).hexdigest()[:10]
    return traj_dir / f"traj_{h}.json"


def _build_headless_args(
    *,
    task: str,
    selected_repo: Optional[str],
    config_file: str = "config.toml",
    name: str = "",
    log_level: Optional[str] = None,
    llm_config: Optional[str] = None,
    agent_config: Optional[str] = None,
    directory: Optional[str] = None,
    max_iterations: Optional[int] = None,
    max_budget_per_task: Optional[float] = None,
    no_auto_continue: bool = False,
) -> argparse.Namespace:
    """Construct a Namespace compatible with setup_config_from_args **without** parse_arguments()."""
    # Mirrors add_common_arguments + add_headless_specific_arguments
    return argparse.Namespace(
        # common
        config_file=config_file,
        task=task,
        file=None,               # -f/--file not used
        name=name,
        log_level=log_level,
        llm_config=llm_config,
        agent_config=agent_config,
        version=False,
        # headless-specific
        directory=directory,
        agent_cls=None,          # or set your default agent class name
        max_iterations=max_iterations,
        max_budget_per_task=max_budget_per_task,
        no_auto_continue=no_auto_continue,
        selected_repo=selected_repo,
        # NOTE: do NOT add save_trajectory here; it isn't parsed. We set on config directly.
    )


def _extract_pr_url_from_json(obj: Any) -> Optional[str]:
    """Recursively walk a JSON-like structure to find a GitHub PR URL."""
    import re
    PR_RE = re.compile(r"https://github\.com/[^/\s]+/[^/\s]+/pull/\d+")
    if isinstance(obj, str):
        m = PR_RE.search(obj)
        return m.group(0) if m else None
    if isinstance(obj, dict):
        for v in obj.values():
            hit = _extract_pr_url_from_json(v)
            if hit:
                return hit
    elif isinstance(obj, list):
        for v in obj:
            hit = _extract_pr_url_from_json(v)
            if hit:
                return hit
    return None


def _ensure_git_identity():
    """Helpful defaults so git commits/PRs don't fail due to missing identity."""
    os.environ.setdefault("GIT_AUTHOR_NAME", "OpenHands Agent")
    os.environ.setdefault("GIT_AUTHOR_EMAIL", "agent@example.com")
    os.environ.setdefault("GIT_COMMITTER_NAME", "OpenHands Agent")
    os.environ.setdefault("GIT_COMMITTER_EMAIL", "agent@example.com")


# ------------------------
# Public API
# ------------------------

async def run_openhands_task_with_pr_async(
    *,
    project_name: str,
    repo: str,
    task: str,
    github_token: Optional[str] = None,
    auto_continue: bool = True,
    appauthor: Optional[str] = None,
    name: str = "",
    config_file: str = "config.toml",
    log_level: Optional[str] = None,
    llm_config: Optional[str] = None,
    agent_config: Optional[str] = None,
    directory: Optional[str] = None,
    max_iterations: Optional[int] = None,
    max_budget_per_task: Optional[float] = None,
) -> dict:
    """Run OpenHands headlessly against a repo and try to extract a PR URL from its trajectory.

    Returns:
        {
          "sid": str | None,
          "final_state": str | None,
          "pr_url": str | None,
          "trajectory_path": str
        }
    """
    if github_token:
        os.environ["GITHUB_TOKEN"] = github_token

    _ensure_git_identity()

    traj_path = _make_traj_path(project_name, task, appauthor=appauthor)

    args = _build_headless_args(
        task=task,
        selected_repo=repo,
        config_file=config_file,
        name=name,
        log_level=log_level or os.getenv("OPENHANDS_LOG_LEVEL", None),
        llm_config=llm_config,
        agent_config=agent_config,
        directory=directory,
        max_iterations=max_iterations,
        max_budget_per_task=max_budget_per_task,
        no_auto_continue=not auto_continue,
    )

    # Turn Namespace -> OpenHands config object
    config = setup_config_from_args(args)

    # Wire the exact field the main loop checks:
    config.save_trajectory_path = str(traj_path)
    # Defensive: ensure the repo is set on the sandbox
    if getattr(config, "sandbox", None):
        config.sandbox.selected_repo = repo

    # Kick off the task
    state = await run_controller(
        config=config,
        initial_user_action=MessageAction(content=task),
        fake_user_response_fn=auto_continue_response if auto_continue else None,
    )

    result = {
        "sid": getattr(state, "sid", None),
        "final_state": state.agent_state.name if state else None,
        "pr_url": None,
        "trajectory_path": str(traj_path),
    }

    # Parse trajectory for a PR URL (robust recursive search)
    try:
        with open(traj_path, "r", encoding="utf-8") as f:
            hist = json.load(f)
        result["pr_url"] = _extract_pr_url_from_json(hist)
    except FileNotFoundError:
        # Leave pr_url as None; caller can inspect logs/agent state
        pass
    except Exception:
        # Keep silent here; add logging if desired
        pass

    return result


def run_openhands_task_with_pr(
    *,
    project_name: str,
    repo: str,
    task: str,
    github_token: Optional[str] = None,
    auto_continue: bool = True,
    appauthor: Optional[str] = None,
    **kwargs,
) -> dict:
    """Synchronous convenience wrapper.

    IMPORTANT: This **must not** be called from within a running event loop.
    Prefer the async version in async code paths.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No loop running: safe to create one.
        return asyncio.run(
            run_openhands_task_with_pr_async(
                project_name=project_name,
                repo=repo,
                task=task,
                github_token=github_token,
                auto_continue=auto_continue,
                appauthor=appauthor,
                **kwargs,
            )
        )
    else:
        # A loop is already running; require the async API.
        raise RuntimeError(
            "run_openhands_task_with_pr() called inside an active event loop. "
            "Use 'await run_openhands_task_with_pr_async(...)' instead."
        )
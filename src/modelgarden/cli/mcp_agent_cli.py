"""
CLI entrypoint for the MCP agent.

Example:
    python -m precursor.cli.mcp_agent_cli \
        --project "AutoMetrics Release" \
        --task "Compile seminar progress summary" \
        --context path/to/context.md \
        --model openai/gpt-5
"""

from __future__ import annotations
import argparse
from pathlib import Path

import dspy
from precursor.agents.mcp_agent import MCPAgent
from precursor.scratchpad import render as scratchpad_render

# Load .env so OPENAI_API_KEY and other secrets are available when launched via python -m
from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("precursor.tools").setLevel(logging.INFO)

def _read_text(path: str | None) -> str:
    if not path:
        return ""
    p = Path(path).expanduser()
    return p.read_text(encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Run MCPAgent on a project + task")
    ap.add_argument("--project", required=True, help="Project name (must exist in projects.yaml)")
    ap.add_argument("--task", required=True, help="Primary task description")
    ap.add_argument(
        "--context",
        help="Optional path to extra project context (markdown or text). "
             "If omitted, the project's scratchpad will be rendered and used.",
    )
    ap.add_argument("--model", default="openai/gpt-5", help="DSPy model id (e.g., openai/gpt-5)")
    args = ap.parse_args()

    # Configure DSPy
    lm = dspy.LM(args.model, temperature=1.0, max_tokens=24000)
    dspy.configure(lm=lm)

    # Prefer provided context file; otherwise render scratchpad for the project
    project_context = _read_text(args.context) if args.context else scratchpad_render.render_project_scratchpad(args.project)
    agent = MCPAgent(model=lm)
    res = agent.run(
        project_name=args.project,
        project_context=project_context,
        task_context=args.task,
    )

    print(res.message)
    if res.artifact_uri:
        print(f"\n[artifact_uri] {res.artifact_uri}")


if __name__ == "__main__":
    main()
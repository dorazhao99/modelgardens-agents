"""
CLI entrypoint for the MCP agent.

Example:
    python -m modelgarden.cli.mcp_agent_cli \
        --task "Create a Google Doc summarizing how to dress for running in different weather conditions" \
        --model openai/gpt-4o
"""

from __future__ import annotations
import argparse
from pathlib import Path

import dspy
from modelgarden.agents.mcp_agent import MCPAgent
# from modelgarden.db.db import render_project_scratchpad

# Load .env so OPENAI_API_KEY and other secrets are available when launched via python -m
from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("modelgarden.tools").setLevel(logging.INFO)

def _read_text(path: str | None) -> str:
    if not path:
        return ""
    p = Path(path).expanduser()
    return p.read_text(encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Run MCPAgent on a project + task")
    ap.add_argument("--task", required=True, help="Primary task description")
    ap.add_argument("--model", default="openai/gpt-5", help="DSPy model id (e.g., openai/gpt-5)")
    args = ap.parse_args()

    # Configure DSPy
    lm = dspy.LM(args.model, temperature=1.0, max_tokens=24000)
    dspy.configure(lm=lm)

    # Prefer provided context file; otherwise render scratchpad for the project
    
    task = """
    Delete the event SALT Lab Meeting on 12/10/2025.

    """
    agent = MCPAgent(model=lm)
    res = agent.run(
        task_context=task,
    )

    print(res.message)
    if res.artifact_uri:
        print(f"\n[artifact_uri] {res.artifact_uri}")


if __name__ == "__main__":
    main()
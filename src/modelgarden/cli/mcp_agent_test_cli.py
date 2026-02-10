"""
CLI entrypoint for the MCP agent.

Example:
    python -m modelgarden.cli.mcp_agent_test_cli \
        --task "Create a Google Doc summarizing how to dress for running in different weather conditions" \
        --model openai/gpt-4o
"""

from __future__ import annotations
import argparse, json, sys
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
   
    with open("/Users/dorazhao/Documents/modelgardens-agents/test/personalized_agent_prompts_v3_baseline.json", "r") as f:
        tasks = json.load(f)
    
    output = {}
    for idx in tasks.keys():
        try:
            print(idx)
            task = tasks[idx]
            logging.info("TASK: %s", task)
            agent = MCPAgent(model=lm)
            res = agent.run(
                task_context=task,
            )

            logging.info("OUTPUT: %s", res.message)
            if res.artifact_uri:
                print(f"\n[artifact_uri] {res.artifact_uri}")
                output[idx] = {"message": res.message, "artifact_uri": res.artifact_uri}
            else:
                output[idx] = {"message": res.message, "artifact_uri": None}
        except Exception as e:
            logging.error("ERROR: %s", e)
            output[idx] = {"message": str(e), "artifact_uri": None}
            continue
    with open("/Users/dorazhao/Documents/modelgardens-agents/test/personalized_agent_output_v3_baseline.json", "w") as f:
        json.dump(output, f)

if __name__ == "__main__":
    main()
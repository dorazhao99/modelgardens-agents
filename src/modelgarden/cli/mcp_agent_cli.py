"""
CLI entrypoint for the MCP agent.

Example:
    python -m modelgarden.cli.mcp_agent_cli \
        --task "Create a Google Doc summarizing how to dress for running in different weather conditions" \
        --model openai/gpt-4o
"""

from __future__ import annotations
import argparse, sys, os
from pathlib import Path

import dspy
from modelgarden.agents.mcp_agent import MCPAgent

# Load .env so OPENAI_API_KEY and other secrets are available when launched via python -m
from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("modelgarden.tools").setLevel(logging.INFO)


def check_credentials(credentials_path: str = "") -> dict:
    """Check for required credentials and provide helpful feedback."""
    issues = []
    warnings = []
    
    # Check OpenAI API key
    if not os.environ.get("OPENAI_API_KEY"):
        issues.append("OPENAI_API_KEY not found in environment")
    
    # Check Google Drive credentials (optional but recommended)
    credentials_path = os.path.join(credentials_path, "credentials.json")
    
    if not os.path.exists(credentials_path):
        warnings.append(f"Google Drive credentials not found at: {credentials_path}")
        warnings.append("  Google Drive features will be unavailable.")
        warnings.append("  Run 'python setup_credentials.py' for setup instructions.")
    
    return {
        "issues": issues,
        "warnings": warnings,
        "has_critical_issues": len(issues) > 0,
        "has_drive": os.path.exists(credentials_path)
    }


def safe_print(msg):
    """Print with error handling for closed file descriptors."""
    try:
        print(msg)
        sys.stdout.flush()
    except (ValueError, OSError, AttributeError):
        # Stdout is closed or unavailable, ignore
        pass

def main() -> dict:
    try:
        parser = argparse.ArgumentParser(description="Run MCP Agent CLI")
        parser.add_argument("--model", default="openai/gpt-5", help="Model to use")
        parser.add_argument("--task", default="Make a travel itinerary for a trip to Munich and save it in the Google Drive folder called 'Travel Itineraries'", help="Task to run")
        parser.add_argument("--credentials", default="", help="Path to Google credentials JSON file")
        args = parser.parse_args()
        model = args.model
        task = args.task
        credentials = args.credentials

        safe_print("=" * 60)
        safe_print("MCP Agent CLI")
        safe_print("=" * 60)
        
        # Check credentials
        cred_check = check_credentials(credentials)
        
        if cred_check["has_critical_issues"]:
            safe_print("\n❌ Critical issues found:")
            for issue in cred_check["issues"]:
                safe_print(f"  • {issue}")
            safe_print("\nPlease fix these issues before continuing.")
            safe_print("Run 'python setup_credentials.py' for help.")
            return {"status": "error", "result": "Missing required credentials"}
        
        if cred_check["warnings"]:
            safe_print("\n⚠️  Warnings:")
            for warning in cred_check["warnings"]:
                safe_print(f"  {warning}")
            safe_print("")
        
        if cred_check["has_drive"]:
            safe_print("✓ Google Drive: Enabled")
        else:
            safe_print("○ Google Drive: Disabled (credentials not found)")
        
        safe_print("\n" + "-" * 60 + "\n")
        
        
        
        
        safe_print(f"Model: {model}")
        safe_print(f"Task: {task}\n")
        safe_print(f"Credentials: {credentials}\n")
        # Configure DSPy
        lm = dspy.LM(model, temperature=1.0, max_tokens=24000)
        dspy.configure(lm=lm)
        os.environ["GOOGLE_CREDENTIALS_JSON"] = credentials + "/credentials.json"
        print(os.environ["GOOGLE_CREDENTIALS_JSON"])
        os.environ["GOOGLE_TOKEN_PICKLE"] = credentials + "/token.pickle"
        agent = MCPAgent(model=lm, credentials_path=credentials)
        res = agent.run(
            task_context=task,
        )
        output = {"status": "success", "result": {"message": res.message, "artifact_uri": res.artifact_uri}}
        safe_print(output)
        return output
        
    except Exception as e:
        output = {"status": "error", "result": str(e)}
        safe_print(output)
        return output

if __name__ == "__main__":
    main()
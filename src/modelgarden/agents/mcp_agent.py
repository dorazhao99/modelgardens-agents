"""
MCP-enabled agent.

Loads MCP servers from config, builds a DSPy toolset (MCP + core.*), then runs a
generic ReAct program for a single task. Keep this thin: orchestration only.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import sys
from pathlib import Path

# Add src directory to path if running as script
if __name__ == "__main__":
    src_dir = Path(__file__).parent.parent.parent  # src/modelgarden/agents -> src/
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

import dspy
from modelgarden.mcp_loader.loader import load_enabled_mcp_servers
from modelgarden.toolset.builder import build_toolset
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("modelgarden.tools").setLevel(logging.INFO)

@dataclass
class AgentResult:
    success: bool
    message: str
    artifact_uri: Optional[str] = None


class MCPTaskSignature(dspy.Signature):
    """Generic MCP-enabled project task.

You are a **tool-using agent** with access to multiple MCP servers, including:
    - Google Drive / Docs tools  
    (e.g., `drive.search_files`, `drive.get_file_as_text`,
    `drive.create_google_doc`, `drive.suggest_edit`)
    - Web search tools  
    (e.g., websearch.brave_web_search, fetch.fetch) — use these to gather *factual external context* when needed. Brave allows you to search by query then fetch allows you to get the actual contents of the webpage.
    - Slides creation and export tools  
    (e.g., slides.build_complete_presentation, slides.export_to_pdf) — capable of generating both Markdown and PDF slide decks.
    - Potentially even more custom tools (always check your tool context!)
    

IMPORTANT:  
• You **cannot ask the user questions directly**.  

---------------------------------------------------------------------------
Output contract
---------------------------------------------------------------------------

- `summary`:
    - A short, clear description of what you did, which tools you used,
        and what the final outcome was.
    - The summary should be a short summary that a user can easily understand and use to understand what you did.

- `artifact_uri`:
    - If you produced any documents, files, or other artifacts,
        return the URI of **the most important** artifact.
        Examples:
        • If you edited several docs: return the key doc or folder URL  
    - If no persistent artifact exists, return `""`.
"""
    task_context: str = dspy.InputField(
        description="A description of the task that the agent is trying to complete."
    )
    summary: str = dspy.OutputField(
        description="Short natural-language summary of what you did, which tools you used, and the final outcome."
    )
    artifact_uri: str = dspy.OutputField(
        description="Main URI of any created/edited artifact (PR URL, doc URL, file path, etc.). Empty string if none."
    )


class MCPAgent:
    def __init__(self, model: dspy.LM | None = None, credentials_path: str = "") -> None:
        self.model = model or dspy.settings.lm
        self.credentials_path = credentials_path
    def run(self, task_context: str) -> AgentResult:

        logger = logging.getLogger("modelgarden.agents")

        # 1) Load MCP servers + global allow/deny filter (GOOGLE_CREDENTIALS_JSON from env if set)
        bundle = load_enabled_mcp_servers(credentials_path=self.credentials_path)

        # 2) Build DSPy toolset (MCP + core.* filtered by allow_fn)
        tools = build_toolset(bundle)



        # 3) Run ReAct program
        with dspy.context(lm=self.model):
            react = dspy.ReAct(MCPTaskSignature, tools=tools, max_iters=50)
            result = react(
                task_context=task_context,
            )

        return AgentResult(
            success=True,
            message=result.summary,
            artifact_uri= result.artifact_uri or None,
        )
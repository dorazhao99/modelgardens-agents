"""
Context Builder core tool.

This exposes the ContextBuilderAgent as a callable tool for other agents.
It ALWAYS runs with the 'openai/gpt-5-nano' model to keep it fast/lightweight.
"""

from __future__ import annotations

import os
import dspy
from dotenv import load_dotenv

load_dotenv()

from precursor.agents.context_agent import ContextBuilderAgent

def gather_project_context(project_name: str, task_context: str) -> str:
    """
    Gather the most relevant verbatim document excerpts for a task within a project.

    This tool runs a dedicated context-building sub-agent that:
    - Uses filesystem and Google Drive tools to search, read, and extract content
    - Returns a markdown-formatted list of verbatim excerpts with document titles and URIs
    - ALWAYS uses the 'openai/gpt-5-nano' model (non-configurable)

    Parameters
    ----------
    project_name : str
        The name of the current project (used for scratchpad and context).
    task_context : str
        The primary task to gather context for. The agent searches for docs relevant to this.

    Returns
    -------
    str
        Markdown-formatted list of verbatim document excerpts suitable for immediate use.
        Format example:
            '## **[Document Title]** (uri: [Document URI])\\n\\n[Excerpts]\\n\\n---'
    """
    # Always use gpt-5-nano for the context agent.
    lm = dspy.LM(
        "openai/gpt-5-nano",
        api_key=os.getenv("OPENAI_API_KEY"),
        temperature=1.0,
        max_tokens=24000,
    )
    agent = ContextBuilderAgent(model=lm)
    return agent.run(project_name=project_name, task_context=task_context)


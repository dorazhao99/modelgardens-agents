"""
Context builder agent.

This agent is responsible for gathering the most relevant context to assist with the task.  It is not directly working on the task, but it is working on the project context and task context to gather the most relevant context.
"""

from __future__ import annotations
import dspy
from precursor.mcp_loader.loader import load_selected_mcp_servers
from precursor.config.loader import get_user_profile

from precursor.scratchpad.render import render_project_scratchpad

class ContextBuilderSignature(dspy.Signature):
    """Given a task and some project context, you are to gather the most relevant verbatim document excerpts that are relevant to the task.  You should use the filesystem and drive tools to gather the most relevant excerpts.  You should return a markdown-formatted list of the excerpts.

You are a **tool-using agent** with access to multiple MCP servers, including:
    - Google Drive / Docs tools  
    (e.g., `drive.search_files`, `drive.get_file_as_text`,
    `drive.create_google_doc`, `drive.suggest_edit`)
    - Filesystem tools  
    (e.g., `filesystem.list_files`, `filesystem.read_file`, `filesystem.write_file`)

Your task is to gather the most relevant context to assist with the task.  YOU ARE NOT DIRECTLY WORKING ON THE TASK.

The task is going to be passed on to another agent to work on.  Your job is to gather the most relevant context to assist with the task.

You should use the filesystem and drive tools to gather the most relevant excerpts.  You should return a markdown-formatted list of the excerpts.

Be liberal with the amount of excerpts you return, you may even opt to output the full document!!!

================================================================================

NOTE you have been given WIDE system access, and not every file will actually be associated with the project that you are working on.
When you find files and gather information it is important that you determine which files ARE and ARE NOT assoicated with the current project.

If you find a file that you deem unrelated, then you should not include it in the output.

================================================================================

Please keep your search relatively efficient and focus on finding the most relevant 1-3 documents.  If you really believe more are necessary keep looking, but often the main context can be built from finding the few BEST docs rather than excerpts from EVERY document.

Avoid repeating the same search query multiple times.  If you don't get all the content you want from one query feel free to try another one.  Note that if you think the question is better suited for a general web search (not project search), you can mention that as a part of the final response and return no documents.  Other agents have general web access, but your job is to specifically build project context from filesystem and drive.

NEVER create new documents or files.

---------------------------------------------------------------------------
Output contract
---------------------------------------------------------------------------

- `verbatim_document_excerpts_markdown`:
    - A markdown-formatted list of verbatim document excerpts that are relevant to the task.  These should be formatted as follows:  '## **[Document Title]** (uri: [Document URI])\n\n[Excerpts from the document]\n\n---'  Feel free to make this LONG and detailed.  We want maximum context for the task.
    """
    user_profile: str = dspy.InputField(
        description="A description of the user and their goals for collaboration with the agent"
    )
    project_name: str = dspy.InputField(
        description="Name of the project you are currently working on. Used for scratchpad and artifact logging."
    )
    project_context: str = dspy.InputField(
        description="Optional background context (scratchpad excerpt, notes, goals, file hints, etc.). Do NOT treat this as a new task."
    )
    task_context: str = dspy.InputField(
        description="The single, primary task to complete right now. Drive all tool calls from this."
    )
    verbatim_document_excerpts_markdown: str = dspy.OutputField(
        description="A markdown-formatted list of verbatim document excerpts that are relevant to the task.  These should be formatted as follows:  '## **[Document Title]** (uri: [Document URI])\n\n[Excerpts from the document]\n\n---'  Feel free to make this LONG and detailed.  We want maximum context for the task."
    )


class ContextBuilderAgent:
    def __init__(self, model: dspy.LM | None = None) -> None:
        self.model = model or dspy.settings.lm

    def run(self, project_name: str, task_context: str) -> str:
        # 1) Load only the minimal MCP servers needed for context building
        #    (filesystem + drive), plus global allow/deny filter.
        bundle = load_selected_mcp_servers(["filesystem", "drive"])

        # 2) Build DSPy toolset (MCP + core.* filtered by allow_fn)
        from precursor.toolset.builder import build_toolset
        tools = build_toolset(bundle)

        # filter to filesystem and drive tools (names start with filesystem. or drive.)
        tools = [tool for tool in tools if tool.name.startswith("filesystem.") or tool.name.startswith("drive.")]

        profile = get_user_profile()

        project_context = render_project_scratchpad(project_name)

        # 3) Run ReAct program
        with dspy.context(lm=self.model):
            react = dspy.ReAct(ContextBuilderSignature, tools=tools, max_iters=30)
            result = react(
                user_profile=profile,
                project_name=project_name,
                project_context=project_context,
                task_context=task_context,
            )

        return result.verbatim_document_excerpts_markdown

if __name__ == "__main__":
    from dotenv import load_dotenv
    import os

    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("precursor.tools").setLevel(logging.INFO)

    load_dotenv()
    lm = dspy.LM("openai/gpt-5-nano", api_key=os.getenv("OPENAI_API_KEY"), temperature=1.0, max_tokens=24000)
    dspy.configure(lm=lm)
    agent = ContextBuilderAgent(model=lm)
    # print(agent.run("Personalization Dataset Collection", "Generate a 5–8 slide deck skeleton plus a one-page executive summary and a 3–5 minute speaker script (saved as GeneralUserModels/gum/docs/irb_packet/{slides.md,summary.md,script.md}) covering objectives, methodology, participant protections/consent plan, technical security appendix, current metrics/status, open questions, and next steps."))
    print(agent.run("Misc", "Produce a one-page EPFL interviewer brief and printable cheat-sheet containing 1-line bios, 1–2 tailored hooks, 3 suggested conversational questions (with 1–2 follow-ups), 1 red-flag phrasing to avoid, and 2 representative paper links for each panel member (Tanja Käser, Sabine Süsstrunk, Martin Jaggi, Martin Schrimpf), and export it as Projects/25_Job apps/EPFL_brief.pdf."))
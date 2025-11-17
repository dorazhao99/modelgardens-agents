import asyncio
import os
import sys
from typing import Any, Dict


# Minimal MCP stdio client to test the Slidev MCP server directly.
# Requires: pip install -U mcp
#
# Usage:
#   # optional: set SLIDEV_DIR to control where .md is written
#   export SLIDEV_DIR="$HOME/precursor-slidev"
#   python dev/scripts/test_slidev_mcp.py
#
# If you need to override the server path:
#   SLIDEV_MCP_SERVER=/absolute/path/to/index.js python dev/scripts/test_slidev_mcp.py


DEFAULT_SERVER_PATH = (
    "/Users/michaelryan/Documents/School/Stanford/Research/"
    "background-agents/src/precursor/mcp_servers/slides/src/index.js"
)


async def main() -> None:
    # Lazy import with helpful error if package missing
    try:
        from mcp import ClientSession, StdioServerParameters  # type: ignore
        from mcp.client.stdio import stdio_client  # type: ignore
    except Exception:
        print(
            "ERROR: Python MCP client is not installed or outdated. "
            "Try: pip install -U mcp",
            file=sys.stderr,
        )
        raise

    server_path = os.environ.get("SLIDEV_MCP_SERVER", DEFAULT_SERVER_PATH)
    if not os.path.isabs(server_path):
        server_path = os.path.abspath(server_path)

    if not os.path.exists(server_path):
        print(f"ERROR: MCP server entry not found at: {server_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Connecting to Slidev MCP server at: {server_path}")

    # Define stdio server parameters to spawn Node process
    params = StdioServerParameters(command="node", args=[server_path])

    # Open stdio connection and create a session
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize
            init = await session.initialize()
            print(f"Initialized: {init}")

            # List tools
            tools = await session.list_tools()
            print("Tools:")
            for t in tools.tools:
                name = t.get("name") if isinstance(t, dict) else getattr(t, "name", "")
                desc = (
                    t.get("description")
                    if isinstance(t, dict)
                    else getattr(t, "description", "")
                )
                print(f"- {name}: {desc}")

            # Call guidance tool
            guidance_args: Dict[str, Any] = {"presentationType": "academic"}
            guidance = await session.call_tool("get_slidev_guidance", guidance_args)
            print("\nget_slidev_guidance result:")

            guidance_json: Dict[str, Any] | None = None
            last_text = None

            for item in guidance.content:
                item_type = (
                    item.get("type")
                    if isinstance(item, dict)
                    else getattr(item, "type", None)
                )
                if item_type == "text":
                    text = (
                        item.get("text")
                        if isinstance(item, dict)
                        else getattr(item, "text", "")
                    )
                    last_text = text
                    print(text)

            # Try to parse the JSON to extract the sample call
            if last_text is not None:
                try:
                    import json as _json

                    guidance_json = _json.loads(last_text)
                except Exception:
                    guidance_json = None

            if guidance_json and "buildTool" in guidance_json:
                sample = guidance_json["buildTool"].get("sampleCall")
                if isinstance(sample, str):
                    print(
                        "\nSample build_complete_presentation call (from guidance):"
                    )
                    print(sample)

            # Build a minimal presentation (no explicit layouts; server will default)
            build_args: Dict[str, Any] = {
                "name": "mcp_minimal_test",
                "title": "MCP Minimal Test",
                "author": "MCP Tester",
                "theme": "seriph",
                "slides": [
                    {
                        "title": "MCP + Slidev",
                        "content": "This is the cover slide. Layout will default to 'cover'.",
                    },
                    {
                        "title": "Second Slide",
                        "content": "- Bullet A\n- Bullet B\n- Bullet C",
                    },
                ],
            }

            build = await session.call_tool("build_complete_presentation", build_args)
            print("\nbuild_complete_presentation result:")
            build_json = None
            last_build_text = None
            for item in build.content:
                item_type = (
                    item.get("type")
                    if isinstance(item, dict)
                    else getattr(item, "type", None)
                )
                if item_type == "text":
                    text = (
                        item.get("text")
                        if isinstance(item, dict)
                        else getattr(item, "text", "")
                    )
                    last_build_text = text
                    print(text)
            if last_build_text is not None:
                try:
                    import json as _json
                    build_json = _json.loads(last_build_text)
                except Exception:
                    build_json = None

            # Try export_to_pdf using inputPath/outputPath (new simplified interface)
            export_args: Dict[str, Any] = {}
            if build_json and isinstance(build_json, dict) and "filePath" in build_json:
                export_args["inputPath"] = build_json["filePath"]
            pdf = await session.call_tool("export_to_pdf", export_args)
            print("\nexport_to_pdf result:")
            for item in pdf.content:
                item_type = (
                    item.get("type")
                    if isinstance(item, dict)
                    else getattr(item, "type", None)
                )
                if item_type == "text":
                    text = (
                        item.get("text")
                        if isinstance(item, dict)
                        else getattr(item, "text", "")
                    )
                    print(text)


if __name__ == "__main__":
    asyncio.run(main())
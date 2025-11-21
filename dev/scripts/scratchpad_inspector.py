#!/usr/bin/env python3
"""
Simple inspector for the Precursor scratchpad SQLite database.

Features:
- Programmatic helpers: list projects, list entries, render project scratchpad
- CLI: list projects, print raw entries, render a project's scratchpad
- Minimal web UI: browse projects and view rendered scratchpad in browser

The DB path is resolved the same way as the app:
  [user_data_dir]/precursor/scratchpad.db
or override with env PRECURSOR_SCRATCHPAD_DB.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

# Ensure we can import the source package when running from repository
THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[2]  # .../background-agents
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from precursor.scratchpad import store  # type: ignore  # noqa: E402
from precursor.scratchpad import render as scratchpad_render  # type: ignore  # noqa: E402


# --------------------------------------------------------------------------------------
# Programmatic API
# --------------------------------------------------------------------------------------

def get_db_path() -> Path:
    """
    Return the path to the scratchpad database used by the store module.
    """
    # store.get_conn uses an internal resolver; mirror the logic for visibility
    # Prefer the environment override for transparency to callers
    env_path = os.getenv("PRECURSOR_SCRATCHPAD_DB")
    if env_path:
        return Path(env_path)
    # Fallback to making a temp connection and reading its database file from PRAGMA
    conn = store.get_conn()
    try:
        row = conn.execute("PRAGMA database_list").fetchone()
        # PRAGMA database_list returns: seq, name, file
        if row and len(row) >= 3 and row[2]:
            return Path(row[2])
        # If for some reason PRAGMA didn't return a file, use the default known path
        # This mirrors store._get_db_path behavior without importing a private symbol
        from platformdirs import user_data_dir  # local import to avoid extra import at top
        return Path(user_data_dir(appname="precursor")) / "scratchpad.db"
    finally:
        conn.close()


def list_projects() -> List[str]:
    """
    Return a list of distinct project names present in the DB (active entries only).
    """
    store.init_db()
    conn = store.get_conn()
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT project_name
            FROM scratchpad_entries
            WHERE status = 'active'
            ORDER BY project_name ASC
            """
        ).fetchall()
        return [r["project_name"] for r in rows]
    finally:
        conn.close()


def list_entries(project_name: str, section: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Return active entries for a given project (optionally filtered by section).
    """
    store.init_db()
    return store.list_entries(project_name, section=section)


def render_project(project_name: str) -> str:
    """
    Return the human/LLM-friendly rendered scratchpad for a project as text.
    """
    return scratchpad_render.render_project_scratchpad(project_name, skip_sections=[])


# --------------------------------------------------------------------------------------
# Minimal Web UI
# --------------------------------------------------------------------------------------

INDEX_HTML = """<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Precursor Scratchpad Inspector</title>
    <style>
      :root {
        color-scheme: light dark;
        --bg: #ffffff;
        --fg: #111111;
        --muted: #666666;
        --accent: #3b82f6;
      }
      @media (prefers-color-scheme: dark) {
        :root {
          --bg: #0b0b0c;
          --fg: #e5e7eb;
          --muted: #9ca3af;
          --accent: #60a5fa;
        }
      }
      body {
        margin: 0;
        font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, Helvetica, Arial, Apple Color Emoji, Segoe UI Emoji;
        background: var(--bg);
        color: var(--fg);
      }
      header {
        padding: 1rem 1.25rem;
        border-bottom: 1px solid #2224;
        display: flex;
        gap: 1rem;
        align-items: center;
      }
      h1 {
        font-size: 1.1rem;
        margin: 0;
      }
      .muted {
        color: var(--muted);
      }
      main {
        display: grid;
        grid-template-columns: 320px 1fr;
        min-height: calc(100dvh - 61px);
      }
      aside {
        border-right: 1px solid #2224;
        padding: 1rem;
      }
      section {
        padding: 1rem;
      }
      select, button {
        padding: 0.5rem 0.6rem;
        border-radius: 8px;
        border: 1px solid #4446;
        background: transparent;
        color: inherit;
      }
      button {
        cursor: pointer;
      }
      .row {
        display: flex;
        gap: 0.5rem;
        align-items: center;
        margin-bottom: 0.75rem;
      }
      pre {
        white-space: pre-wrap;
        border: 1px solid #4446;
        border-radius: 12px;
        padding: 1rem;
        background: #1112;
        max-width: 1200px;
      }
      .small {
        font-size: 0.85rem;
      }
      .path {
        word-break: break-all;
      }
      .pill {
        display: inline-block;
        padding: 0.15rem 0.5rem;
        border: 1px solid #4446;
        border-radius: 999px;
        font-size: 0.8rem;
      }
      a {
        color: var(--accent);
        text-decoration: none;
      }
    </style>
  </head>
  <body>
    <header>
      <h1>Precursor Scratchpad Inspector</h1>
      <span class="muted small">Browse your scratchpad.db in the browser</span>
    </header>
    <main>
      <aside>
        <div class="row">
          <label for="project">Project</label>
          <select id="project"></select>
        </div>
        <div class="small muted">
          DB Path:
          <span id="dbPath" class="path"></span>
        </div>
      </aside>
      <section>
        <div class="row">
          <button id="refresh">Refresh</button>
          <span id="status" class="muted small"></span>
          <span id="counts" class="pill"></span>
        </div>
        <pre id="rendered">(select a project)</pre>
      </section>
    </main>
    <script>
      const elProject = document.getElementById('project');
      const elRendered = document.getElementById('rendered');
      const elRefresh = document.getElementById('refresh');
      const elStatus = document.getElementById('status');
      const elCounts = document.getElementById('counts');
      const elDbPath = document.getElementById('dbPath');

      async function fetchJson(path) {
        const res = await fetch(path);
        if (!res.ok) throw new Error(await res.text());
        return res.json();
      }
      async function fetchText(path) {
        const res = await fetch(path);
        if (!res.ok) throw new Error(await res.text());
        return res.text();
      }

      async function loadProjects() {
        elStatus.textContent = 'Loading...';
        try {
          const meta = await fetchJson('/api/meta');
          elDbPath.textContent = meta.db_path;
          const data = await fetchJson('/api/projects');
          elProject.innerHTML = '';
          for (const name of data.projects) {
            const opt = document.createElement('option');
            opt.value = name;
            opt.textContent = name;
            elProject.appendChild(opt);
          }
          if (data.projects.length > 0) {
            elProject.value = data.projects[0];
            await loadProject();
          } else {
            elRendered.textContent = '(no projects in DB)';
            elCounts.textContent = '';
            elStatus.textContent = '';
          }
        } catch (err) {
          elStatus.textContent = 'Failed to load';
          elRendered.textContent = String(err);
        }
      }

      async function loadProject() {
        const project = elProject.value;
        if (!project) return;
        elStatus.textContent = 'Loading...';
        try {
          const rendered = await fetchText('/api/render?project=' + encodeURIComponent(project));
          const entries = await fetchJson('/api/entries?project=' + encodeURIComponent(project));
          elRendered.textContent = rendered;
          elCounts.textContent = entries.entries.length + ' entries';
          elStatus.textContent = '';
        } catch (err) {
          elStatus.textContent = 'Failed to load';
          elRendered.textContent = String(err);
          elCounts.textContent = '';
        }
      }

      elProject.addEventListener('change', loadProject);
      elRefresh.addEventListener('click', loadProject);
      loadProjects();
    </script>
  </body>
</html>
""".strip()


class ApiHandler(BaseHTTPRequestHandler):
    def _send_json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text: str, status: int = 200) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str, status: int = 200) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            qs = parse_qs(parsed.query)

            if path == "/":
                return self._send_html(INDEX_HTML)

            if path == "/api/meta":
                return self._send_json(
                    {
                        "db_path": str(get_db_path()),
                        "version": 1,
                    }
                )

            if path == "/api/projects":
                return self._send_json({"projects": list_projects()})

            if path == "/api/entries":
                project = (qs.get("project") or [""])[0]
                if not project:
                    return self._send_json({"error": "missing project"}, status=400)
                entries = list_entries(project)
                return self._send_json({"entries": entries})

            if path == "/api/render":
                project = (qs.get("project") or [""])[0]
                if not project:
                    return self._send_text("missing project", status=400)
                text = render_project(project)
                return self._send_text(text)

            self.send_error(404, "Not Found")
        except Exception as e:
            # Return basic error JSON/text depending on path
            try:
                self._send_json({"error": str(e)}, status=500)
            except Exception:
                self._send_text(str(e), status=500)


def serve(port: int = 8765, host: str = "127.0.0.1") -> None:
    """
    Run a tiny HTTP server with a minimal UI.
    """
    store.init_db()
    httpd = HTTPServer((host, port), ApiHandler)
    print(f"Scratchpad inspector running at http://{host}:{port} (DB: {get_db_path()})")
    httpd.serve_forever()


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------

def _cli() -> None:
    parser = argparse.ArgumentParser(description="Inspect the Precursor scratchpad DB.")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("db-path", help="Print the resolved scratchpad DB path")

    sub.add_parser("list-projects", help="List projects present in the DB")

    p_list = sub.add_parser("list", help="List entries for a project")
    p_list.add_argument("project", help="Project name")
    p_list.add_argument("--section", help="Optional section filter", default=None)
    p_list.add_argument("--json", action="store_true", help="Output JSON instead of text")

    p_render = sub.add_parser("render", help="Render a project's scratchpad to text")
    p_render.add_argument("project", help="Project name")

    p_serve = sub.add_parser("serve", help="Start a minimal web UI")
    p_serve.add_argument("--port", type=int, default=8765, help="Port to listen on")
    p_serve.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind")

    args = parser.parse_args()

    if args.cmd == "db-path":
        print(get_db_path())
        return

    if args.cmd == "list-projects":
        projects = list_projects()
        if not projects:
            print("(no projects)")
            return
        for p in projects:
            print(p)
        return

    if args.cmd == "list":
        rows = list_entries(args.project, section=args.section)
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
            return
        if not rows:
            print("(no entries)")
            return
        for r in rows:
            # mirror the common fields; include id for reference
            msg = r.get("message", "")
            conf = r.get("confidence", 0)
            section = r.get("section", "")
            subsection = r.get("subsection")
            rid = r.get("id")
            prefix = f"[{section}{' / ' + subsection if subsection else ''}]"
            print(f"#{rid} {prefix} {msg} (confidence: {conf})")
        return

    if args.cmd == "render":
        print(render_project(args.project), end="")
        return

    if args.cmd == "serve":
        serve(port=args.port, host=args.host)
        return

    parser.print_help()


if __name__ == "__main__":
    _cli()


# Example usage:
# python dev/scripts/scratchpad_inspector.py serve --port 8765

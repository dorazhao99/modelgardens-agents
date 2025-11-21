#!/usr/bin/env python3
"""
Quick CSV annotation UI for utility and feasibility ratings.

Features:
- Displays only project (or project_name) and task_description per row
- Two rubrics: annotated_utility_score and annotated_feasibility_score (1-5)
- Keyboard shortcuts:
  - Keys 1–5: fill the next missing annotation (utility first, then feasibility)
  - Left Arrow: save and go to previous row
  - Right Arrow: save and go to next row
- Buttons for setting 1–5 on each rubric, and Prev/Next buttons
- Saves to CSV whenever you move rows and when you click a score button
- Allows navigating back (Left Arrow) to fix previous annotations; saves to correct row

Run:
  python -m dev.scripts.annotate --csv dev/survey/data_collection/11_20_experiments/combined_for_annotation.csv --port 8765
Then open http://127.0.0.1:8765 in your browser.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List, Tuple

try:
    from flask import Flask, jsonify, redirect, render_template_string, request, url_for
except Exception as e:  # pragma: no cover
    raise SystemExit("Flask is required for this tool. Install with: pip install flask") from e


HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>CSV Annotator</title>
    <style>
      body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin: 24px; line-height: 1.4; }
      .container { max-width: 960px; margin: 0 auto; }
      .meta { color: #555; margin-bottom: 12px; }
      .card { border: 1px solid #ddd; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
      .title { font-size: 16px; color: #333; margin: 4px 0; }
      .task { white-space: pre-wrap; }
      .rubric { margin-top: 8px; }
      .rubric h3 { margin: 6px 0; font-size: 14px; }
      .buttons { display: flex; gap: 8px; flex-wrap: wrap; }
      .buttons button { padding: 8px 10px; border-radius: 6px; border: 1px solid #aaa; background: #f8f8f8; cursor: pointer; }
      .buttons button.selected { background: #2563eb; color: white; border-color: #1d4ed8; }
      .nav { display: flex; justify-content: space-between; margin-top: 14px; }
      .nav button { padding: 8px 12px; border-radius: 6px; border: 1px solid #aaa; background: #f0f0f0; cursor: pointer; }
      .kbd { background: #eee; border-radius: 4px; padding: 2px 6px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; }
      .help { color: #666; font-size: 13px; margin-top: 8px; }
      .dim { color: #777; }
    </style>
  </head>
  <body>
    <div class="container">
      <div class="meta">
        Row {{ idx+1 }} / {{ total }} &nbsp; <span class="dim">|</span> &nbsp; Saved to: <span class="dim">{{ csv_path }}</span>
      </div>
      <div class="card">
        <div class="title"><strong>Project:</strong> {{ project_display }}</div>
        <div class="title"><strong>Task:</strong></div>
        <div class="task">{{ task_description }}</div>
      </div>

      <div class="card rubric" id="rubric-utility">
        <h3>Utility (annotated_utility_score)</h3>
        <div class="help">1: Do not want an agent to attempt this • 2: Not interested • 3: Neutral • 4: Happy agent attempted • 5: Excited agent might do this</div>
        <div class="buttons">
          {% for n in [1,2,3,4,5] %}
          <button data-field="annotated_utility_score" data-value="{{ n }}" class="{% if utility_value == n|string %}selected{% endif %}">{{ n }}</button>
          {% endfor %}
        </div>
      </div>

      <div class="card rubric" id="rubric-feasibility">
        <h3>Feasibility (annotated_feasibility_score)</h3>
        <div class="help">1: Certain the agent won't do this right • 2: Concerned • 3: Uncertain • 4: Believe agent can • 5: Certain agent can</div>
        <div class="buttons">
          {% for n in [1,2,3,4,5] %}
          <button data-field="annotated_feasibility_score" data-value="{{ n }}" class="{% if feasibility_value == n|string %}selected{% endif %}">{{ n }}</button>
          {% endfor %}
        </div>
      </div>

      <div class="nav">
        <button id="prevBtn" {% if idx == 0 %}disabled{% endif %}>← Prev (Left Arrow)</button>
        <button id="nextBtn" {% if idx+1 >= total %}disabled{% endif %}>Next (Right Arrow) →</button>
      </div>

      <div class="help">
        Keyboard: <span class="kbd">1..5</span> fills next missing score (utility → feasibility). <span class="kbd">←</span> previous row. <span class="kbd">→</span> next row.
      </div>
    </div>

    <script>
      const state = {
        idx: {{ idx }},
        total: {{ total }},
        csvPath: {{ csv_path | tojson }},
        utility: {{ utility_value | tojson }},
        feasibility: {{ feasibility_value | tojson }},
      };

      async function saveScores() {
        const payload = {
          idx: state.idx,
          annotated_utility_score: state.utility || "",
          annotated_feasibility_score: state.feasibility || "",
        };
        const res = await fetch("/api/update", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!res.ok) {
          console.error("Failed to save", res.status);
        }
      }

      function selectButton(field, value) {
        const group = document.querySelectorAll('button[data-field="' + field + '"]');
        group.forEach(b => {
          if (b.getAttribute("data-value") === String(value)) {
            b.classList.add("selected");
          } else {
            b.classList.remove("selected");
          }
        });
      }

      async function setScore(field, value, save=true) {
        if (field === "annotated_utility_score") {
          state.utility = String(value);
          selectButton(field, value);
        } else if (field === "annotated_feasibility_score") {
          state.feasibility = String(value);
          selectButton(field, value);
        }
        if (save) {
          await saveScores();
        }
      }

      async function go(delta) {
        await saveScores();
        const nextIdx = Math.min(Math.max(0, state.idx + delta), state.total - 1);
        if (nextIdx !== state.idx) {
          const url = new URL(window.location.href);
          url.searchParams.set("idx", String(nextIdx));
          window.location.href = url.toString();
        }
      }

      function handleNumberKey(num) {
        // Fill next missing: utility first, then feasibility
        if (!state.utility) {
          setScore("annotated_utility_score", num, true);
        } else {
          setScore("annotated_feasibility_score", num, true);
        }
      }

      document.addEventListener("DOMContentLoaded", () => {
        document.querySelectorAll(".buttons button").forEach(btn => {
          btn.addEventListener("click", async (e) => {
            const field = e.currentTarget.getAttribute("data-field");
            const value = e.currentTarget.getAttribute("data-value");
            await setScore(field, value, true);
          });
        });

        document.getElementById("prevBnt");
      });

      document.getElementById("prevBtn")?.addEventListener("click", () => go(-1));
      document.getElementById("nextBtn")?.addEventListener("click", () => go(1));

      document.addEventListener("keydown", (e) => {
        // Prevent arrow keys from scrolling page
        if (["ArrowLeft", "ArrowRight"].includes(e.key)) {
          e.preventDefault();
        }
        if (e.key === "ArrowLeft") {
          go(-1);
        } else if (e.key === "ArrowRight") {
          go(1);
        } else if (["1","2","3","4","5"].includes(e.key)) {
          handleNumberKey(parseInt(e.key, 10));
        }
      });
    </script>
  </body>
  </html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Quick CSV annotation interface.")
    parser.add_argument(
        "--csv",
        required=True,
        help="Path to the CSV to annotate (e.g., combined_for_annotation.csv).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port to serve the annotator (default: 8765).",
    )
    return parser.parse_args()


def load_csv(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        headers = [h for h in (reader.fieldnames or []) if h is not None]
        rows = [dict(r) for r in reader]
    # Ensure annotation columns exist
    changed = False
    if "annotated_utility_score" not in headers:
        headers.append("annotated_utility_score")
        changed = True
    if "annotated_feasibility_score" not in headers:
        headers.append("annotated_feasibility_score")
        changed = True
    # Ensure keys exist in rows
    for r in rows:
        if "annotated_utility_score" not in r:
            r["annotated_utility_score"] = ""
        if "annotated_feasibility_score" not in r:
            r["annotated_feasibility_score"] = ""
    return headers, rows


def write_csv(path: Path, headers: List[str], rows: List[Dict[str, str]]) -> None:
    # Ensure all rows have all headers
    for r in rows:
        for h in headers:
            if h not in r:
                r[h] = ""
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def create_app(csv_path: Path) -> Flask:
    app = Flask(__name__)
    headers, rows = load_csv(csv_path)

    @app.get("/")
    def root():
        return redirect(url_for("annotate", idx=0))

    @app.get("/annotate")
    def annotate():
        idx_s = request.args.get("idx", "0")
        try:
            idx = max(0, min(int(idx_s), len(rows) - 1))
        except Exception:
            idx = 0
        row = rows[idx] if rows else {}

        project_display = row.get("project") or row.get("project_name") or ""
        task_description = row.get("task_description") or ""
        utility_value = (row.get("annotated_utility_score") or "").strip()
        feasibility_value = (row.get("annotated_feasibility_score") or "").strip()

        return render_template_string(
            HTML_TEMPLATE,
            idx=idx,
            total=len(rows),
            csv_path=str(csv_path),
            project_display=project_display,
            task_description=task_description,
            utility_value=utility_value,
            feasibility_value=feasibility_value,
        )

    @app.post("/api/update")
    def api_update():
        payload = request.get_json(force=True, silent=True) or {}
        try:
            idx = int(payload.get("idx", -1))
        except Exception:
            return jsonify(ok=False, error="invalid idx"), 400
        if not (0 <= idx < len(rows)):
            return jsonify(ok=False, error="idx out of range"), 400
        util = str(payload.get("annotated_utility_score", "") or "").strip()
        feas = str(payload.get("annotated_feasibility_score", "") or "").strip()
        rows[idx]["annotated_utility_score"] = util
        rows[idx]["annotated_feasibility_score"] = feas
        write_csv(csv_path, headers, rows)
        return jsonify(ok=True)

    return app


def main() -> None:
    args = parse_args()
    csv_path = Path(args.csv).expanduser().resolve()
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")
    app = create_app(csv_path)
    print(f"Open http://127.0.0.1:{args.port} to annotate {csv_path}")
    app.run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()



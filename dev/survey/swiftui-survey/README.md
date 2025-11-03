## SurveyApp (macOS, SwiftUI)

This is a minimal SwiftUI macOS app that collects a short survey and appends results to `dev/survey/survey_responses.csv`.

### Questions
- What project are you working on right now?
- What task are you working on right now?
- What background context could be helpful with this task?
- What background context could be helpful with this project?
- What background work would have been helpful for this task?
- What background context would have been helpful with this project?

### Build & Run

Requirements: Xcode 15+ or Swift 5.9+ on macOS 13+

Option A — Run from Xcode:
1. Open this folder in Xcode (`File` → `Open...` → select `dev/survey/swiftui-survey`).
2. Xcode will detect the Swift Package. Select the `SurveyApp` scheme.
3. Run (⌘R).

Option B — Build and run via command line:
```bash
cd dev/survey/swiftui-survey
swift build -c release
.build/release/SurveyApp
```

### Output
Responses are appended to `dev/survey/survey_responses.csv` with the following columns:
`timestamp, project_now, task_now, helpful_task_context_now, helpful_project_context_now, helpful_task_background_work_past, helpful_project_background_context_past`


## AgentResultsApp (macOS, SwiftUI)

A visually polished viewer for background agent updates. It shows a header like:
“Here's what I worked on for {project_name} while you were gone” and a list of results. Each card displays the task description, a summary of agent messages (expandable), and actions:

- View: Opens the `artifact_uri` in the default browser (http/https) or Finder/app (file path or file URL)
- Reject: Simulates rejecting/closing the item (removes from the list). Hooks are provided to integrate with your system later.

### Data format

The app accepts either a single JSON payload or a bare array of results.

Payload shape:
```json
{
  "projectName": "AutoMetrics",
  "results": [
    {
      "success": true,
      "message": "- Created new Google Doc...",
      "artifact_uri": "https://docs.google.com/...",
      "task_description": "Finalize and compile a detailed summary..."
    }
  ]
}
```

Or a bare array:
```json
[
  {
    "success": true,
    "message": "- Created new Google Doc...",
    "artifact_uri": "file:///Users/me/Documents/Slides.key",
    "task_description": "Create a polished slide deck..."
  }
]
```

### Build & Run

Requirements: Xcode 15+ or Swift 5.9+ on macOS 13+

Option A — Run from Xcode:
1. Open this folder in Xcode (`File` → `Open...` → select `dev/survey/swiftui-survey`).
2. Select the `AgentResultsApp` scheme.
3. Run (⌘R).

Option B — Command line with sample data:
```bash
cd dev/survey/swiftui-survey
swift run AgentResultsApp
```

Option C — Command line with your own JSON:
```bash
cd dev/survey/swiftui-survey
swift run AgentResultsApp -- --input /absolute/path/to/agent_results.json
# Optionally override project name if the JSON lacks it:
swift run AgentResultsApp -- --input /path/to/results.json --project "My Project"
```

Notes:
- The `--` before flags ensures SwiftPM forwards arguments to the app.
- `artifact_uri` may be `https://...`, `file:///...`, or a plain absolute file path.

### Integration hooks

`AgentResultsApp` defines a lightweight protocol to hook into user actions:

```swift
protocol AgentResultActionHandler {
    func didOpen(result: AgentResultItem)
    func didReject(result: AgentResultItem)
}
```

By default the app uses a `DefaultActionHandler` that logs to stdout. You can later inject an implementation that updates files, records analytics, or triggers follow-up background work.


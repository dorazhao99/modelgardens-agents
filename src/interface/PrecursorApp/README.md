## PrecursorApp (macOS, SwiftUI)

An aesthetic viewer for agent-completed tasks pulled directly from `scratchpad.db`. It merges:

- Agent Completed Tasks (Pending Review): view, accept, or reject
- Accepted Agent Completed Tasks: view only

Rejected items are hidden. Entries are grouped into soft time buckets (Today, Yesterday, This Week, Last Week, This Month, Last Month, Last 6 Months, This Year, Last Year) shown only when they contain items.

A pill-style project picker at the top lets you switch projects.

### Data source

This app reads directly from the SQLite database used by Precursor:

- Default path (macOS): `~/Library/Application Support/precursor/scratchpad.db`
- Override via env var: `PRECURSOR_SCRATCHPAD_DB=/absolute/path/to/scratchpad.db`

Expected sections:

- `Agent Completed Tasks (Pending Review)`
- `Accepted Agent Completed Tasks`
- `Rejected Agent Completed Tasks` (hidden)

Metadata keys used when present:

- `task` (title), `short_description`, `step_by_step_summary`, `uri` (used for View action)

### Build & Run

Requirements: Xcode 15+ or Swift 5.9+ on macOS 13+

Option A — Run from Xcode:
1. Open this folder in Xcode (`File` → `Open...` → select `interface/PrecursorApp`).
2. Xcode will detect the Swift Package. Select the `PrecursorApp` scheme.
3. Run (⌘R).

Option B — Command line:
```bash
cd interface/PrecursorApp
swift run PrecursorApp
```

With a custom DB path:
```bash
cd interface/PrecursorApp
PRECURSOR_SCRATCHPAD_DB="/absolute/path/to/scratchpad.db" swift run PrecursorApp
```

### Notes

- Accept moves an item to `Accepted Agent Completed Tasks`.
- Reject moves an item to `Rejected Agent Completed Tasks` (and removes it from the view).
- The app preserves your existing visual style (glass background, soft shadows, subtle pills). 



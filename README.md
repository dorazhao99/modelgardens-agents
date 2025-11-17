# background-agents
Repo for the Background Agents Rotation Project

## For Slides

```bash
cd src/precursor/mcp_servers/slides
npm run setup
```

## macOS Notifications → Launch PrecursorApp

This project can send a macOS notification from Python that, when clicked, launches the SwiftUI app focused on a specific project.

### Prereqs
- macOS 13+
- Swift 5.9+ (Xcode or Command Line Tools)
- terminal-notifier
  ```bash
  brew install terminal-notifier
  ```

### Run the Swift UI
```bash
cd src/interface/PrecursorApp
swift run PrecursorApp
```
With a specific project:
```bash
swift run PrecursorApp --project "<project_name>"
```

### Trigger via Python
`UIManager.run_for_project("<project>")` on macOS shows a notification; clicking it runs:
```bash
swift run PrecursorApp --project "<project>"
```
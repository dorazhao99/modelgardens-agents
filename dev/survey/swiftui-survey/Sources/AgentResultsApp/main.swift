import SwiftUI
import AppKit

// MARK: - Models

struct AgentResultItem: Identifiable, Codable, Equatable {
    let id: UUID
    let success: Bool
    let message: String
    let artifactURI: String?
    let taskDescription: String

    init(id: UUID = UUID(), success: Bool, message: String, artifactURI: String?, taskDescription: String) {
        self.id = id
        self.success = success
        self.message = message
        self.artifactURI = artifactURI
        self.taskDescription = taskDescription
    }

    enum CodingKeys: String, CodingKey {
        case id
        case success
        case message
        case artifactURI = "artifact_uri"
        case taskDescription = "task_description"
    }
}

struct AgentResultsPayload: Codable {
    let projectName: String
    let results: [AgentResultItem]
}

// MARK: - Action Handler Hook

protocol AgentResultActionHandler {
    func didOpen(result: AgentResultItem)
    func didReject(result: AgentResultItem)
}

final class DefaultActionHandler: AgentResultActionHandler {
    func didOpen(result: AgentResultItem) {
        // Placeholder for integrating with your system (e.g., update logs/files)
        print("Opened: \(result.taskDescription)")
    }
    func didReject(result: AgentResultItem) {
        // Placeholder for integrating with your system (e.g., revert changes)
        print("Rejected: \(result.taskDescription)")
    }
}

// MARK: - App State

final class AgentResultsState: ObservableObject {
    @Published var projectName: String
    @Published var results: [AgentResultItem]
    var actionHandler: AgentResultActionHandler

    init(projectName: String, results: [AgentResultItem], actionHandler: AgentResultActionHandler = DefaultActionHandler()) {
        self.projectName = projectName
        self.results = results
        self.actionHandler = actionHandler
    }

    func open(_ result: AgentResultItem) {
        guard let uri = result.artifactURI, !uri.isEmpty else { return }
        if let url = URL(string: uri), url.scheme == "http" || url.scheme == "https" || url.scheme == "file" {
            NSWorkspace.shared.open(url)
            actionHandler.didOpen(result: result)
            return
        }
        // Treat as local file path
        let fileURL = URL(fileURLWithPath: uri)
        NSWorkspace.shared.open(fileURL)
        actionHandler.didOpen(result: result)
    }

    func reject(_ result: AgentResultItem) {
        withAnimation(.spring(response: 0.4, dampingFraction: 0.8)) {
            results.removeAll { $0.id == result.id }
        }
        actionHandler.didReject(result: result)
    }
}

// MARK: - UI

struct AgentResultsAppView: View {
    @ObservedObject var state: AgentResultsState
    @State private var expanded: Set<UUID> = []

    var body: some View {
        ZStack {
            LinearGradient(colors: [Color(nsColor: .controlAccentColor).opacity(0.35), .black.opacity(0.6)], startPoint: .topLeading, endPoint: .bottomTrailing)
                .ignoresSafeArea()

            VStack(alignment: .leading, spacing: 18) {
                header
                content
            }
            .padding(24)
        }
        .frame(minWidth: 900, minHeight: 620)
    }

    private var header: some View {
        HStack(alignment: .center) {
            VStack(alignment: .leading, spacing: 6) {
                Text("Here's what I worked on for")
                    .font(.system(size: 14, weight: .medium))
                    .foregroundStyle(.secondary)
                Text(state.projectName)
                    .font(.system(size: 28, weight: .bold))
                    .foregroundStyle(.white)
                    .shadow(color: .black.opacity(0.25), radius: 8, x: 0, y: 2)
            }
            Spacer()
            Capsule()
                .fill(.ultraThinMaterial)
                .overlay(
                    HStack(spacing: 10) {
                        Image(systemName: "bolt.fill")
                            .symbolRenderingMode(.palette)
                            .foregroundStyle(.yellow, .white.opacity(0.7))
                        Text("Background Agent Updates")
                            .font(.system(size: 13, weight: .semibold))
                            .foregroundStyle(.primary)
                    }
                    .padding(.horizontal, 14)
                )
                .frame(height: 36)
                .shadow(color: .black.opacity(0.25), radius: 8, x: 0, y: 4)
        }
    }

    private var content: some View {
        ScrollView {
            LazyVStack(spacing: 16) {
                ForEach(state.results) { result in
                    AgentResultCard(
                        result: result,
                        isExpanded: expanded.contains(result.id),
                        toggleExpanded: { toggleExpanded(for: result) },
                        onOpen: { state.open(result) },
                        onReject: { state.reject(result) }
                    )
                    .transition(.asymmetric(insertion: .opacity.combined(with: .scale(scale: 0.98)), removal: .move(edge: .trailing).combined(with: .opacity)))
                }
                if state.results.isEmpty {
                    emptyState
                        .padding(.top, 40)
                }
            }
        }
    }

    private var emptyState: some View {
        VStack(spacing: 10) {
            Image(systemName: "checkmark.seal.fill")
                .font(.system(size: 48))
                .foregroundStyle(.green)
            Text("All caught up")
                .font(.system(size: 18, weight: .semibold))
                .foregroundStyle(.white)
            Text("No pending agent updates")
                .foregroundStyle(.secondary)
        }
        .padding(28)
        .frame(maxWidth: .infinity)
        .background(.ultraThinMaterial)
        .cornerRadius(14)
        .overlay(
            RoundedRectangle(cornerRadius: 14)
                .stroke(.white.opacity(0.08), lineWidth: 1)
        )
    }

    private func toggleExpanded(for result: AgentResultItem) {
        if expanded.contains(result.id) {
            expanded.remove(result.id)
        } else {
            expanded.insert(result.id)
        }
    }
}

struct AgentResultCard: View {
    let result: AgentResultItem
    let isExpanded: Bool
    let toggleExpanded: () -> Void
    let onOpen: () -> Void
    let onReject: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top, spacing: 12) {
                statusIcon
                VStack(alignment: .leading, spacing: 6) {
                    Text(result.taskDescription)
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(.primary)
                    messageSection
                }
                Spacer()
            }
            actionRow
        }
        .padding(18)
        .background(.ultraThinMaterial)
        .cornerRadius(14)
        .overlay(
            RoundedRectangle(cornerRadius: 14)
                .stroke(.white.opacity(0.08), lineWidth: 1)
        )
        .shadow(color: .black.opacity(0.2), radius: 10, x: 0, y: 6)
    }

    private var statusIcon: some View {
        ZStack {
            Circle()
                .fill(result.success ? Color.green.opacity(0.2) : Color.red.opacity(0.2))
                .frame(width: 36, height: 36)
            Image(systemName: result.success ? "checkmark" : "xmark")
                .font(.system(size: 14, weight: .bold))
                .foregroundStyle(result.success ? .green : .red)
        }
    }

    private var messageSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(result.message)
                .foregroundStyle(.secondary)
                .lineLimit(isExpanded ? nil : 3)
                .animation(.easeInOut(duration: 0.2), value: isExpanded)
            Button(action: toggleExpanded) {
                HStack(spacing: 4) {
                    Text(isExpanded ? "Show less" : "Show more")
                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .font(.system(size: 11, weight: .semibold))
                }
                .font(.system(size: 12, weight: .semibold))
            }
            .buttonStyle(.plain)
            .foregroundStyle(.primary)
            .opacity(result.message.count > 180 ? 1 : 0)
        }
    }

    private var actionRow: some View {
        HStack(spacing: 10) {
            if let uri = result.artifactURI, !uri.isEmpty {
                Button(action: onOpen) {
                    Label("View", systemImage: "arrow.up.right.square")
                        .font(.system(size: 13, weight: .semibold))
                        .padding(.horizontal, 14)
                        .padding(.vertical, 8)
                        .background(
                            LinearGradient(colors: [Color(nsColor: .controlAccentColor), Color(nsColor: .controlAccentColor).opacity(0.8)], startPoint: .leading, endPoint: .trailing)
                        )
                        .foregroundStyle(.white)
                        .cornerRadius(10)
                        .shadow(color: Color(nsColor: .controlAccentColor).opacity(0.4), radius: 8, x: 0, y: 4)
                }
                .buttonStyle(.plain)
                .help(uri)
            }

            Button(role: .destructive, action: onReject) {
                Label("Reject", systemImage: "xmark")
                    .font(.system(size: 13, weight: .semibold))
                    .padding(.horizontal, 14)
                    .padding(.vertical, 8)
                    .background(Color.red.opacity(0.12))
                    .foregroundStyle(.red)
                    .cornerRadius(10)
            }
            .buttonStyle(.plain)

            Spacer()
        }
    }
}

// MARK: - App Entrypoint

@main
struct AgentResultsAppMain: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        WindowGroup {
            AgentResultsAppView(state: makeInitialState())
        }
        .windowStyle(.hiddenTitleBar)
    }

    private func makeInitialState() -> AgentResultsState {
        if let payload = loadPayloadFromCLI() {
            return AgentResultsState(projectName: payload.projectName, results: payload.results)
        }
        return AgentResultsState(projectName: samplePayload.projectName, results: samplePayload.results)
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
    }
}

// MARK: - CLI / Loading

private func loadPayloadFromCLI() -> AgentResultsPayload? {
    // Supported flags:
    // --input /path/to/payload.json
    // --project "Project Name" (used only if JSON omits projectName)
    let args = CommandLine.arguments
    var inputPath: String?
    var overrideProject: String?

    var i = 0
    while i < args.count {
        let arg = args[i]
        if arg == "--input", i + 1 < args.count { inputPath = args[i + 1]; i += 1 }
        if arg == "--project", i + 1 < args.count { overrideProject = args[i + 1]; i += 1 }
        i += 1
    }

    guard let inputPath else { return nil }
    let url = URL(fileURLWithPath: inputPath)
    guard let data = try? Data(contentsOf: url) else { return nil }
    // Try decoding as full payload first
    if let payload = try? JSONDecoder().decode(AgentResultsPayload.self, from: data) {
        if let name = overrideProject, !name.isEmpty {
            return AgentResultsPayload(projectName: name, results: payload.results)
        }
        return payload
    }
    // Fallback: decode bare array of results and wrap
    if let results = try? JSONDecoder().decode([AgentResultItem].self, from: data) {
        return AgentResultsPayload(projectName: overrideProject ?? "Project", results: results)
    }
    return nil
}

// MARK: - Sample Data

private let samplePayload = AgentResultsPayload(
    projectName: "AutoMetrics Release",
    results: [
        AgentResultItem(
            success: true,
            message: "- Searched Drive for existing seminar summary (none found).\n- Created new Google Doc: “AutoMetrics - Stanford AI Seminar Summary (10/17)”.\n- Added comprehensive content: overview, objective statuses (page.tsx refactor, integration, API monitoring, Firestore rules, docs/slides), risks and mitigations (Firebase connectivity, rules, integration regressions, performance, messaging), prioritized next steps, readiness checklist, and resource links.\n- Delivered the document link for team access and final reviews.",
            artifactURI: "https://docs.google.com/document/d/166U819E0a9nNTLr33AmZB2kik3QQHjLdb3zSdNQ5Q0Y/edit",
            taskDescription: "Finalize and compile a detailed summary of project objectives and progress for the Stanford AI Seminar on 10/17."
        ),
        AgentResultItem(
            success: true,
            message: "Submitted pull request to XenonMolecule/autometrics-site (https://github.com/XenonMolecule/autometrics-site/pull/new/precursor-refactor-1761931188)",
            artifactURI: "https://github.com/XenonMolecule/autometrics-site/pull/new/precursor-refactor-1761931188",
            taskDescription: "Refactor the code in page.tsx to improve performance, ensuring clarity in the project documentation."
        )
    ]
)



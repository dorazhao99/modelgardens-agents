import SwiftUI
import AppKit
import Foundation
import SQLite3

var initialProjectFromCLI: String?

private func parseCLIArgs() {
    let args = CommandLine.arguments
    guard args.count > 1 else { return }
    var i = 1
    while i < args.count {
        let arg = args[i]
        if arg == "--project", i + 1 < args.count {
            initialProjectFromCLI = args[i + 1]
            i += 2
        } else {
            i += 1
        }
    }
}

// MARK: - Models

enum TaskStatus: String {
    case pending = "Agent Completed Tasks (Pending Review)"
    case accepted = "Accepted Agent Completed Tasks"
}

struct AgentTaskItem: Identifiable, Equatable {
    let id: Int64
    let projectName: String
    let status: TaskStatus
    let message: String
    let createdAt: Date
    let metadata: [String: Any]

    static func == (lhs: AgentTaskItem, rhs: AgentTaskItem) -> Bool {
        return lhs.id == rhs.id
    }

    var uri: String? {
        (metadata["uri"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines)
    }
    var taskTitle: String {
        if let t = (metadata["task"] as? String), !t.isEmpty { return t }
        // Fallback: try to extract before " (uri:" if present
        if let idx = message.firstIndex(of: "(") {
            return String(message[..<idx]).trimmingCharacters(in: .whitespacesAndNewlines)
        }
        return message
    }
    var shortDescription: String? {
        (metadata["short_description"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines)
    }
    var stepByStepSummary: String? {
        (metadata["step_by_step_summary"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines)
    }
}

// MARK: - SQLite Client

final class SQLiteClient {
    private var db: OpaquePointer?

    init() {}

    deinit {
        close()
    }

    func open() throws {
        if db != nil { return }
        let path = Self.resolveDatabasePath()
        var handle: OpaquePointer?
        let rc = path.withCString { sqlite3_open($0, &handle) }
        if rc != SQLITE_OK {
            throw NSError(domain: "SQLite", code: 1, userInfo: [NSLocalizedDescriptionKey: "Unable to open database at \(path)"])
        }
        db = handle
    }

    func close() {
        if let d = db {
            sqlite3_close(d)
            db = nil
        }
    }

    static func resolveDatabasePath() -> String {
        let env = ProcessInfo.processInfo.environment
        if let override = env["PRECURSOR_SCRATCHPAD_DB"], !override.isEmpty {
            return override
        }
        // ~/Library/Application Support/precursor/scratchpad.db
        let urls = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)
        let base = urls.first ?? URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent("Library/Application Support")
        let dir = base.appendingPathComponent("precursor", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let path = dir.appendingPathComponent("scratchpad.db").path
        return path
    }

    func listProjects() throws -> [String] {
        try open()
        let sql = """
        SELECT DISTINCT project_name
        FROM scratchpad_entries
        WHERE status = 'active'
          AND section IN (?, ?)
        ORDER BY project_name COLLATE NOCASE ASC
        """
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else {
            throw sqliteError("prepare listProjects")
        }
        defer { sqlite3_finalize(stmt) }
        bindText(stmt, 1, TaskStatus.pending.rawValue)
        bindText(stmt, 2, TaskStatus.accepted.rawValue)

        var results: [String] = []
        while sqlite3_step(stmt) == SQLITE_ROW {
            if let cStr = sqlite3_column_text(stmt, 0) {
                results.append(String(cString: cStr))
            }
        }
        return results
    }

    func listTasks(projectName: String) throws -> [AgentTaskItem] {
        try open()
        let sql = """
        SELECT id, project_name, section, message, created_at, metadata_json
        FROM scratchpad_entries
        WHERE status = 'active'
          AND project_name = ?
          AND section IN (?, ?)
        ORDER BY datetime(created_at) DESC
        """
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else {
            throw sqliteError("prepare listTasks")
        }
        defer { sqlite3_finalize(stmt) }
        bindText(stmt, 1, projectName)
        bindText(stmt, 2, TaskStatus.pending.rawValue)
        bindText(stmt, 3, TaskStatus.accepted.rawValue)

        var items: [AgentTaskItem] = []
        while sqlite3_step(stmt) == SQLITE_ROW {
            let id = sqlite3_column_int64(stmt, 0)
            let proj = String(cString: sqlite3_column_text(stmt, 1))
            let section = String(cString: sqlite3_column_text(stmt, 2))
            let message = String(cString: sqlite3_column_text(stmt, 3))
            let createdAtStr = String(cString: sqlite3_column_text(stmt, 4))
            var metadata: [String: Any] = [:]
            if let metaText = sqlite3_column_text(stmt, 5) {
                let data = Data(String(cString: metaText).utf8)
                if let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                    metadata = obj
                }
            }
            let status: TaskStatus = (section == TaskStatus.accepted.rawValue) ? .accepted : .pending
            let createdAt = DateFormatter.sqlite.date(from: createdAtStr) ?? Date()
            let item = AgentTaskItem(
                id: id,
                projectName: proj,
                status: status,
                message: message,
                createdAt: createdAt,
                metadata: metadata
            )
            items.append(item)
        }
        return items
    }

    func updateTaskSection(id: Int64, to newSection: TaskStatus) throws {
        try open()
        let sql = """
        UPDATE scratchpad_entries
        SET section = ?
        WHERE id = ?
        """
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else {
            throw sqliteError("prepare updateTaskSection")
        }
        defer { sqlite3_finalize(stmt) }
        bindText(stmt, 1, newSection.rawValue)
        sqlite3_bind_int64(stmt, 2, id)
        guard sqlite3_step(stmt) == SQLITE_DONE else {
            throw sqliteError("step updateTaskSection")
        }
    }

    func updateTaskSectionRaw(id: Int64, to newSection: String) throws {
        try open()
        let sql = """
        UPDATE scratchpad_entries
        SET section = ?
        WHERE id = ?
        """
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else {
            throw sqliteError("prepare updateTaskSectionRaw")
        }
        defer { sqlite3_finalize(stmt) }
        bindText(stmt, 1, newSection)
        sqlite3_bind_int64(stmt, 2, id)
        guard sqlite3_step(stmt) == SQLITE_DONE else {
            throw sqliteError("step updateTaskSectionRaw")
        }
    }

    private func sqliteError(_ whereMsg: String) -> NSError {
        let errMsg = String(cString: sqlite3_errmsg(db))
        return NSError(domain: "SQLite", code: 2, userInfo: [NSLocalizedDescriptionKey: "\(whereMsg): \(errMsg)"])
    }

    private func bindText(_ stmt: OpaquePointer?, _ index: Int32, _ value: String) {
        _ = value.withCString { cStr in
            sqlite3_bind_text(stmt, index, cStr, -1, SQLITE_TRANSIENT)
        }
    }
}

private let SQLITE_TRANSIENT = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

private extension DateFormatter {
    static let sqlite: DateFormatter = {
        let df = DateFormatter()
        df.locale = Locale(identifier: "en_US_POSIX")
        df.dateFormat = "yyyy-MM-dd HH:mm:ss"
        return df
    }()
}

// MARK: - Grouping

struct TimeBucket: Hashable {
    let title: String
}

private func bucketTitle(for date: Date, now: Date = Date()) -> String {
    let cal = Calendar.current
    if cal.isDateInToday(date) { return "Today" }
    if cal.isDateInYesterday(date) { return "Yesterday" }

    let weekOfYearNow = cal.component(.weekOfYear, from: now)
    let weekOfYearDate = cal.component(.weekOfYear, from: date)
    let yearNow = cal.component(.yearForWeekOfYear, from: now)
    let yearDate = cal.component(.yearForWeekOfYear, from: date)
    if yearNow == yearDate && weekOfYearNow == weekOfYearDate { return "This Week" }
    if yearNow == yearDate && weekOfYearNow == weekOfYearDate + 1 { return "Last Week" }

    let monthNow = cal.component(.month, from: now)
    let monthDate = cal.component(.month, from: date)
    let yearCalNow = cal.component(.year, from: now)
    let yearCalDate = cal.component(.year, from: date)
    if yearCalNow == yearCalDate && monthNow == monthDate { return "This Month" }
    if yearCalNow == yearCalDate && monthNow == monthDate + 1 { return "Last Month" }

    if let sixMonthsAgo = cal.date(byAdding: .month, value: -6, to: now), date >= sixMonthsAgo {
        return "Last 6 Months"
    }
    if cal.component(.year, from: date) == cal.component(.year, from: now) {
        return "This Year"
    }
    return "Last Year"
}

private func groupTasks(_ tasks: [AgentTaskItem]) -> [(String, [AgentTaskItem])] {
    var grouped: [String: [AgentTaskItem]] = [:]
    for t in tasks {
        let title = bucketTitle(for: t.createdAt)
        grouped[title, default: []].append(t)
    }
    // Sort groups by recency, and items within each group by recency desc
    let order = ["Today","Yesterday","This Week","Last Week","This Month","Last Month","Last 6 Months","This Year","Last Year"]
    let sortedKeys = grouped.keys.sorted { a, b in
        let ia = order.firstIndex(of: a) ?? order.count
        let ib = order.firstIndex(of: b) ?? order.count
        if ia != ib { return ia < ib }
        return a < b
    }
    return sortedKeys.map { key in
        let items = grouped[key]?.sorted(by: { $0.createdAt > $1.createdAt }) ?? []
        return (key, items)
    }
}

// MARK: - App State

final class AppState: ObservableObject {
    @Published var projects: [String] = []
    @Published var selectedProject: String? = nil
    @Published var tasks: [AgentTaskItem] = []
    @Published var errorMessage: String? = nil
    @Published var isLoading: Bool = false

    private let db = SQLiteClient()

    func loadInitial() {
        isLoading = true
        errorMessage = nil
        DispatchQueue.global(qos: .userInitiated).async {
            do {
                let projs = try self.db.listProjects()
                var selected = self.selectedProject
                if selected == nil { selected = projs.first }
                let items = selected != nil ? try self.db.listTasks(projectName: selected!) : []
                DispatchQueue.main.async {
                    self.projects = projs
                    self.selectedProject = selected
                    self.tasks = items
                    self.isLoading = false
                }
            } catch {
                DispatchQueue.main.async {
                    self.errorMessage = error.localizedDescription
                    self.isLoading = false
                }
            }
        }
    }

    func reloadTasks() {
        guard let project = selectedProject else { return }
        isLoading = true
        errorMessage = nil
        DispatchQueue.global(qos: .userInitiated).async {
            do {
                let items = try self.db.listTasks(projectName: project)
                DispatchQueue.main.async {
                    self.tasks = items
                    self.isLoading = false
                }
            } catch {
                DispatchQueue.main.async {
                    self.errorMessage = error.localizedDescription
                    self.isLoading = false
                }
            }
        }
    }

    func selectProject(_ project: String) {
        selectedProject = project
        reloadTasks()
    }

    func accept(_ task: AgentTaskItem) {
        DispatchQueue.global(qos: .userInitiated).async {
            do {
                try self.db.updateTaskSection(id: task.id, to: .accepted)
                DispatchQueue.main.async {
                    // update local copy
                    if let idx = self.tasks.firstIndex(of: task) {
                        self.tasks[idx] = AgentTaskItem(
                            id: task.id,
                            projectName: task.projectName,
                            status: .accepted,
                            message: task.message,
                            createdAt: task.createdAt,
                            metadata: task.metadata
                        )
                    }
                }
            } catch {
                DispatchQueue.main.async {
                    self.errorMessage = error.localizedDescription
                }
            }
        }
    }

    func reject(_ task: AgentTaskItem) {
        DispatchQueue.global(qos: .userInitiated).async {
            do {
                // Move to Rejected; app hides rejected
                try self.db.updateTaskSectionRaw(id: task.id, to: "Rejected Agent Completed Tasks")
                DispatchQueue.main.async {
                    self.tasks.removeAll { $0.id == task.id }
                }
            } catch {
                DispatchQueue.main.async {
                    self.errorMessage = error.localizedDescription
                }
            }
        }
    }
}

// MARK: - UI

struct PrecursorAppView: View {
    @ObservedObject var state: AppState
    let initialProject: String?
    @State private var expanded: Set<Int64> = []
    @State private var showSettings: Bool = false

    var headerGradient: some View {
        LinearGradient(colors: [Color(nsColor: .controlAccentColor).opacity(0.35), .black.opacity(0.6)],
                       startPoint: .topLeading, endPoint: .bottomTrailing)
            .ignoresSafeArea()
    }

    var body: some View {
        ZStack {
            headerGradient
            VStack(alignment: .leading, spacing: 18) {
                header
                projectPickerBar
                content
            }
            .padding(24)
        }
        .frame(minWidth: 1000, minHeight: 680)
        .onAppear {
            if let proj = initialProject {
                state.selectedProject = proj
            }
            state.loadInitial()
        }
        .sheet(isPresented: $showSettings) {
            SettingsSheetView(isPresented: $showSettings)
                .frame(minWidth: 760, minHeight: 540)
        }
    }

    private var header: some View {
        HStack(alignment: .center) {
            VStack(alignment: .leading, spacing: 6) {
                Text("Here's what I worked on for")
                    .font(.system(size: 14, weight: .medium))
                    .foregroundStyle(.secondary)
                Text(state.selectedProject ?? "—")
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
                        Text("Precursor Agent Updates")
                            .font(.system(size: 13, weight: .semibold))
                            .foregroundStyle(.primary)
                    }
                    .padding(.horizontal, 14)
                )
                .frame(height: 36)
                .shadow(color: .black.opacity(0.25), radius: 8, x: 0, y: 4)
            Button(action: { showSettings = true }) {
                Image(systemName: "gearshape.fill")
                    .font(.system(size: 14, weight: .bold))
                    .padding(10)
                    .background(.ultraThinMaterial)
                    .foregroundStyle(.primary)
                    .cornerRadius(10)
                    .shadow(color: .black.opacity(0.2), radius: 6, x: 0, y: 4)
            }
            .buttonStyle(.plain)
        }
    }

    private var projectPickerBar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 10) {
                ForEach(state.projects, id: \.self) { project in
                    let selected = (project == state.selectedProject)
                    Button(action: { state.selectProject(project) }) {
                        HStack(spacing: 8) {
                            Image(systemName: selected ? "checkmark.seal.fill" : "seal")
                                .font(.system(size: 12, weight: .semibold))
                                .foregroundStyle(selected ? .white : .secondary)
                            Text(project)
                                .font(.system(size: 13, weight: .semibold))
                        }
                        .padding(.horizontal, 14)
                        .padding(.vertical, 8)
                        .background(
                            ZStack {
                                if selected {
                                    LinearGradient(colors: [Color(nsColor: .controlAccentColor), Color(nsColor: .controlAccentColor).opacity(0.8)], startPoint: .leading, endPoint: .trailing)
                                } else {
                                    Color.white.opacity(0.08)
                                }
                            }
                        )
                        .foregroundStyle(selected ? .white : .primary)
                        .cornerRadius(10)
                        .shadow(color: selected ? Color(nsColor: .controlAccentColor).opacity(0.35) : .clear, radius: 8, x: 0, y: 4)
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.vertical, 2)
        }
    }

    private var content: some View {
        Group {
            if state.isLoading {
                ProgressView().progressViewStyle(.circular)
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .center)
            } else if let error = state.errorMessage {
                Text(error).foregroundStyle(.red)
            } else if state.tasks.isEmpty {
                emptyState
            } else {
                ScrollView {
                    LazyVStack(spacing: 16) {
                        ForEach(groupTasks(state.tasks), id: \.0) { (title, items) in
                            if !items.isEmpty {
                                GroupHeader(title: title)
                                    .padding(.top, 6)
                                ForEach(items) { item in
                                    AgentTaskCard(
                                        item: item,
                                        isExpanded: expanded.contains(item.id),
                                        toggleExpanded: { toggleExpanded(for: item) },
                                        onView: { open(item) },
                                        onAccept: { state.accept(item) },
                                        onReject: { state.reject(item) }
                                    )
                                    .transition(.asymmetric(insertion: .opacity.combined(with: .scale(scale: 0.98)), removal: .move(edge: .trailing).combined(with: .opacity)))
                                }
                            }
                        }
                    }
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
            Text("No pending or accepted agent updates")
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

    private func toggleExpanded(for item: AgentTaskItem) {
        if expanded.contains(item.id) {
            expanded.remove(item.id)
        } else {
            expanded.insert(item.id)
        }
    }

    private func open(_ item: AgentTaskItem) {
        guard let uri = item.uri, !uri.isEmpty else { return }
        if let url = URL(string: uri), ["http", "https", "file"].contains(url.scheme?.lowercased() ?? "") {
            NSWorkspace.shared.open(url)
            return
        }
        let fileURL = URL(fileURLWithPath: uri)
        NSWorkspace.shared.open(fileURL)
    }
}

struct GroupHeader: View {
    let title: String
    var body: some View {
        HStack {
            Text(title)
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(.secondary)
            Spacer()
        }
        .padding(.horizontal, 6)
    }
}

struct AgentTaskCard: View {
    let item: AgentTaskItem
    let isExpanded: Bool
    let toggleExpanded: () -> Void
    let onView: () -> Void
    let onAccept: () -> Void
    let onReject: () -> Void

    var statusPill: some View {
        let color: Color = (item.status == .pending) ? .yellow : .green
        let text: String = (item.status == .pending) ? "Pending Review" : "Accepted"
        return HStack(spacing: 6) {
            Circle().fill(color).frame(width: 8, height: 8)
            Text(text)
                .font(.system(size: 11, weight: .semibold))
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(Color.white.opacity(0.06))
        .cornerRadius(8)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top, spacing: 12) {
                ZStack {
                    Circle()
                        .fill((item.status == .accepted ? Color.green : Color.yellow).opacity(0.18))
                        .frame(width: 36, height: 36)
                    Image(systemName: item.status == .accepted ? "checkmark" : "clock")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundStyle(item.status == .accepted ? .green : .yellow)
                }
                VStack(alignment: .leading, spacing: 6) {
                    HStack {
                        Text(item.shortDescription ?? item.taskTitle)
                            .font(.system(size: 16, weight: .semibold))
                            .foregroundStyle(.primary)
                        Spacer()
                        statusPill
                    }
                    // Expanded details
                    if isExpanded {
                        if let steps = item.stepByStepSummary, !steps.isEmpty {
                            Text(steps)
                                .font(.system(size: 12))
                                .foregroundStyle(.secondary)
                        }
                        Text("(Agent Task: \(item.taskTitle))")
                            .font(.system(size: 12))
                            .foregroundStyle(.secondary)
                    }
                    let hasDetails = (item.stepByStepSummary?.isEmpty == false) || (!item.taskTitle.isEmpty)
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
                    .opacity(hasDetails ? 1 : 0)
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

    private var actionRow: some View {
        HStack(spacing: 10) {
            if let uri = item.uri, !uri.isEmpty {
                Button(action: onView) {
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

            if item.status == .pending {
                Button(action: onAccept) {
                    Label("Accept", systemImage: "checkmark")
                        .font(.system(size: 13, weight: .semibold))
                        .padding(.horizontal, 14)
                        .padding(.vertical, 8)
                        .background(Color.green.opacity(0.12))
                        .foregroundStyle(.green)
                        .cornerRadius(10)
                }
                .buttonStyle(.plain)

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
            }

            Spacer()
        }
    }
}

// MARK: - App Entrypoint

@main
struct PrecursorAppMain: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var state = AppState()

    init() {
        parseCLIArgs()
    }

    var body: some Scene {
        WindowGroup {
            PrecursorAppView(state: state, initialProject: initialProjectFromCLI)
        }
        .windowStyle(.hiddenTitleBar)
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag {
            // If no visible windows, bring back the main SwiftUI window(s)
            for window in sender.windows {
                window.makeKeyAndOrderFront(self)
            }
        }
        return true
    }
}

// MARK: - Settings models and YAML I/O

struct ProjectConfig: Identifiable, Hashable {
    let id = UUID()
    var name: String
    var description: String
    var agentEnabled: Bool
}

struct UserConfig {
    var name: String
    var description: String
    var agentGoals: String
}

struct SystemSettingsConfig {
    var valueWeight: Double
    var feasibilityWeight: Double
    var userPreferenceAlignmentWeight: Double
    var maxDeployedTasks: Int
    var deploymentThreshold: Double
    var safetyThreshold: Int
    // Transition sensitivities
    var departureTimeThresholdMinutes: Double
    var departureMinEntriesPreviousSegment: Int
    var arrivalTimeThresholdMinutes: Double
    var arrivalMinEntriesCurrentSegment: Int
    // Observation source cooldown (seconds)
    var observationCooldownSeconds: Double
}

enum ConfigPathKind {
    case projects
    case user
    case settings
}

enum ConfigIO {
    static func resolvePath(_ kind: ConfigPathKind) -> URL? {
        let env = ProcessInfo.processInfo.environment
        switch kind {
        case .projects:
            if let p = env["PRECURSOR_PROJECTS_FILE"], !p.isEmpty { return URL(fileURLWithPath: p) }
        case .user:
            if let p = env["PRECURSOR_USER_FILE"], !p.isEmpty { return URL(fileURLWithPath: p) }
        case .settings:
            if let p = env["PRECURSOR_SETTINGS_FILE"], !p.isEmpty { return URL(fileURLWithPath: p) }
        }
        // Fallback: search upwards for src/precursor/config/<file>.yaml from CWD
        let fileName: String
        switch kind {
        case .projects: fileName = "projects.yaml"
        case .user: fileName = "user.yaml"
        case .settings: fileName = "settings.yaml"
        }
        let fm = FileManager.default
        var dir = URL(fileURLWithPath: fm.currentDirectoryPath)
        for _ in 0..<8 {
            let candidate = dir.appendingPathComponent("src/precursor/config/\(fileName)")
            if fm.fileExists(atPath: candidate.path) {
                return candidate
            }
            let parent = dir.deletingLastPathComponent()
            if parent.path == dir.path { break }
            dir = parent
        }
        return nil
    }

    private static func existingHeader(at url: URL) -> String? {
        let fm = FileManager.default
        guard fm.fileExists(atPath: url.path),
              let text = try? String(contentsOf: url, encoding: .utf8)
        else { return nil }
        var headerLines: [String] = []
        for raw in text.split(separator: "\n", omittingEmptySubsequences: false) {
            let line = String(raw)
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if trimmed.hasPrefix("#") || trimmed.isEmpty {
                headerLines.append(line)
            } else {
                break
            }
        }
        return headerLines.isEmpty ? nil : headerLines.joined(separator: "\n") + "\n"
    }

    // Minimal YAML parsing tailored to our files
    static func loadUser() throws -> UserConfig {
        guard let path = resolvePath(.user) else { throw NSError(domain: "Config", code: 1, userInfo: [NSLocalizedDescriptionKey: "user.yaml not found"]) }
        let text = try String(contentsOf: path, encoding: .utf8)
        var name = ""
        var description = ""
        var goals = ""
        var currentKey: String?
        var collectingBlock: [String] = []
        func flushBlock() {
            guard let k = currentKey else { return }
            let joined = collectingBlock.joined(separator: "\n").trimmingCharacters(in: .whitespacesAndNewlines)
            if k == "description" { description = joined }
            if k == "agent_goals" { goals = joined }
            currentKey = nil
            collectingBlock = []
        }
        for raw in text.split(separator: "\n", omittingEmptySubsequences: false) {
            let line = String(raw)
            if line.trimmingCharacters(in: .whitespaces).hasPrefix("#") { continue }
            if line.hasPrefix("name:") {
                flushBlock()
                name = line.replacingOccurrences(of: "name:", with: "").trimmingCharacters(in: .whitespaces).trimmingCharacters(in: CharacterSet(charactersIn: "\""))
                continue
            }
            if line.hasPrefix("description: |") {
                flushBlock()
                currentKey = "description"
                collectingBlock = []
                continue
            }
            if line.hasPrefix("agent_goals: |") {
                flushBlock()
                currentKey = "agent_goals"
                collectingBlock = []
                continue
            }
            if let _ = currentKey {
                if line.hasPrefix("  ") || line.isEmpty {
                    collectingBlock.append(line.hasPrefix("  ") ? String(line.dropFirst(2)) : "")
                } else {
                    flushBlock()
                }
            }
        }
        flushBlock()
        return UserConfig(name: name, description: description, agentGoals: goals)
    }

    static func saveUser(_ u: UserConfig) throws {
        guard let path = resolvePath(.user) else { throw NSError(domain: "Config", code: 2, userInfo: [NSLocalizedDescriptionKey: "user.yaml path not resolved"]) }
        let preservedHeader = existingHeader(at: path)
        let defaultHeader = """
# config/user.yaml
# ---------------------------------------------------------------------------
# User profile / preferences
# ---------------------------------------------------------------------------
# This file is meant for LLM-facing components that want to tailor behavior
# to *you* (priorities, personality, preferences, etc).
# ---------------------------------------------------------------------------

"""
        let header = preservedHeader ?? defaultHeader
        let body =
"""
\(header)name: \"\(u.name)\"
description: |
  \(u.description.replacingOccurrences(of: "\n", with: "\n  "))
agent_goals: |
  \(u.agentGoals.replacingOccurrences(of: "\n", with: "\n  "))
"""
        try body.write(to: path, atomically: true, encoding: .utf8)
    }

    static func loadSettings() throws -> SystemSettingsConfig {
        guard let path = resolvePath(.settings) else { throw NSError(domain: "Config", code: 3, userInfo: [NSLocalizedDescriptionKey: "settings.yaml not found"]) }
        let text = try String(contentsOf: path, encoding: .utf8)
        var map: [String: String] = [:]
        for raw in text.split(separator: "\n") {
            let line = String(raw)
            if line.trimmingCharacters(in: .whitespaces).hasPrefix("#") { continue }
            let parts = line.split(separator: ":", maxSplits: 1).map(String.init)
            if parts.count == 2 {
                map[parts[0].trimmingCharacters(in: .whitespaces)] = parts[1].trimmingCharacters(in: .whitespaces)
            }
        }
        func d(_ k: String, _ def: Double) -> Double { Double(map[k] ?? "") ?? def }
        func i(_ k: String, _ def: Int) -> Int { Int(map[k] ?? "") ?? def }
        return SystemSettingsConfig(
            valueWeight: d("value_weight", 2.0),
            feasibilityWeight: d("feasibility_weight", 1.5),
            userPreferenceAlignmentWeight: d("user_preference_alignment_weight", 0.5),
            maxDeployedTasks: i("max_deployed_tasks", 3),
            deploymentThreshold: d("deployment_threshold", 0.9),
            safetyThreshold: i("safety_threshold", 7),
            departureTimeThresholdMinutes: d("departure_time_threshold_minutes", 3.0),
            departureMinEntriesPreviousSegment: i("departure_min_entries_previous_segment", 3),
            arrivalTimeThresholdMinutes: d("arrival_time_threshold_minutes", 15.0),
            arrivalMinEntriesCurrentSegment: i("arrival_min_entries_current_segment", 1),
            observationCooldownSeconds: d("observation_cooldown_seconds", 60.0)
        )
    }

    static func saveSettings(_ s: SystemSettingsConfig) throws {
        guard let path = resolvePath(.settings) else { throw NSError(domain: "Config", code: 4, userInfo: [NSLocalizedDescriptionKey: "settings.yaml path not resolved"]) }
        let preservedHeader = existingHeader(at: path)
        let defaultHeader = """
# config/settings.yaml
# ---------------------------------------------------------------------------
# Settings for the system as a whole.
# ---------------------------------------------------------------------------
# This file is meant for settings that are used to configure the system.
# In particular the value, feasibility, safety, and user_preference alignment
# decide which tasks are considered for deployment.  The deployment threshold
# ---------------------------------------------------------------------------

"""
        let header = preservedHeader ?? defaultHeader
        let body =
"""
\(header)value_weight: \(formatDouble(s.valueWeight))
feasibility_weight: \(formatDouble(s.feasibilityWeight))
user_preference_alignment_weight: \(formatDouble(s.userPreferenceAlignmentWeight))

max_deployed_tasks: \(s.maxDeployedTasks)
deployment_threshold: \(formatDouble(s.deploymentThreshold))

safety_threshold: \(s.safetyThreshold)

# Notification / transition sensitivities
# ---------------------------------------------------------------------------
departure_time_threshold_minutes: \(formatDouble(s.departureTimeThresholdMinutes))
departure_min_entries_previous_segment: \(s.departureMinEntriesPreviousSegment)

arrival_time_threshold_minutes: \(formatDouble(s.arrivalTimeThresholdMinutes))
arrival_min_entries_current_segment: \(s.arrivalMinEntriesCurrentSegment)

# Observation source cooldown
# ---------------------------------------------------------------------------
observation_cooldown_seconds: \(formatDouble(s.observationCooldownSeconds))
"""
        try body.write(to: path, atomically: true, encoding: .utf8)
    }

    static func loadProjects() throws -> [ProjectConfig] {
        guard let path = resolvePath(.projects) else { throw NSError(domain: "Config", code: 5, userInfo: [NSLocalizedDescriptionKey: "projects.yaml not found"]) }
        let text = try String(contentsOf: path, encoding: .utf8)
        var projects: [ProjectConfig] = []
        var current: ProjectConfig?
        for raw in text.split(separator: "\n", omittingEmptySubsequences: false) {
            let line = String(raw)
            if line.trimmingCharacters(in: .whitespaces).hasPrefix("#") { continue }
            if line.trimmingCharacters(in: .whitespaces) == "projects:" {
                continue
            }
            if line.trimmingCharacters(in: .whitespaces).hasPrefix("- name:") {
                if let c = current { projects.append(c) }
                let name = line.components(separatedBy: ":").dropFirst().joined(separator: ":").trimmingCharacters(in: CharacterSet.whitespacesAndNewlines).trimmingCharacters(in: CharacterSet(charactersIn: "\""))
                current = ProjectConfig(name: name.trimmingCharacters(in: CharacterSet(charactersIn: "\"")), description: "", agentEnabled: true)
                continue
            }
            if line.trimmingCharacters(in: .whitespaces).hasPrefix("description:") {
                let val = line.components(separatedBy: ":").dropFirst().joined(separator: ":").trimmingCharacters(in: .whitespaces)
                let desc = val.trimmingCharacters(in: CharacterSet(charactersIn: "\""))
                current?.description = desc
                continue
            }
            if line.trimmingCharacters(in: .whitespaces).hasPrefix("agent_enabled:") {
                let val = line.components(separatedBy: ":").dropFirst().joined(separator: ":").trimmingCharacters(in: .whitespaces)
                current?.agentEnabled = (val.lowercased().hasPrefix("t"))
                continue
            }
        }
        if let c = current { projects.append(c) }
        return projects
    }

    static func saveProjects(_ projects: [ProjectConfig]) throws {
        guard let path = resolvePath(.projects) else { throw NSError(domain: "Config", code: 6, userInfo: [NSLocalizedDescriptionKey: "projects.yaml path not resolved"]) }
        let preservedHeader = existingHeader(at: path)
        var lines: [String] = []
        if let header = preservedHeader {
            lines.append(contentsOf: header.split(separator: "\n").map(String.init))
        } else {
            lines.append("# config/projects.yaml")
            lines.append("# ---------------------------------------------------------------------------")
            lines.append("# Project Registry")
            lines.append("# ---------------------------------------------------------------------------")
            lines.append("")
        }
        lines.append("projects:")
        for p in projects {
            lines.append("  - name: \"\(p.name)\"")
            lines.append("    description: \"\(p.description.replacingOccurrences(of: "\"", with: "\\\""))\"")
            lines.append("    agent_enabled: \(p.agentEnabled ? "true" : "false")")
            lines.append("")
        }
        try lines.joined(separator: "\n").write(to: path, atomically: true, encoding: .utf8)
    }

    private static func formatDouble(_ v: Double) -> String {
        if v.rounded(.toNearestOrAwayFromZero) == v { return String(format: "%.0f", v) }
        return String(format: "%.3f", v)
    }
}

final class SettingsViewModel: ObservableObject {
    @Published var projects: [ProjectConfig] = []
    @Published var user = UserConfig(name: "", description: "", agentGoals: "")
    @Published var settings = SystemSettingsConfig(
        valueWeight: 2.0, feasibilityWeight: 1.5, userPreferenceAlignmentWeight: 0.5,
        maxDeployedTasks: 3, deploymentThreshold: 0.9, safetyThreshold: 7,
        departureTimeThresholdMinutes: 3.0, departureMinEntriesPreviousSegment: 3,
        arrivalTimeThresholdMinutes: 15.0, arrivalMinEntriesCurrentSegment: 1,
        observationCooldownSeconds: 60.0
    )
    @Published var errorMessage: String? = nil
    @Published var savedBanner: String? = nil

    func loadAll() {
        do {
            projects = try ConfigIO.loadProjects()
            user = try ConfigIO.loadUser()
            settings = try ConfigIO.loadSettings()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func saveProjects() {
        do {
            try ConfigIO.saveProjects(projects)
            savedBanner = "Projects saved"
        } catch {
            errorMessage = error.localizedDescription
        }
    }
    func saveUser() {
        do {
            try ConfigIO.saveUser(user)
            savedBanner = "User profile saved"
        } catch {
            errorMessage = error.localizedDescription
        }
    }
    func saveSettings() {
        do {
            try ConfigIO.saveSettings(settings)
            savedBanner = "System settings saved"
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

// MARK: - Settings UI

struct SettingsSheetView: View {
    @Binding var isPresented: Bool
    @StateObject private var vm = SettingsViewModel()
    @State private var tab: Int = 0

    var body: some View {
        ZStack {
            LinearGradient(colors: [Color(nsColor: .controlAccentColor).opacity(0.25), .black.opacity(0.5)], startPoint: .topLeading, endPoint: .bottomTrailing)
                .ignoresSafeArea()
            VStack(alignment: .leading, spacing: 16) {
                HStack {
                    Label("Settings", systemImage: "gearshape.fill")
                        .font(.system(size: 22, weight: .bold))
                        .foregroundStyle(.white)
                        .shadow(color: .black.opacity(0.25), radius: 8, x: 0, y: 2)
                    Spacer()
                    Button(action: { isPresented = false }) {
                        Image(systemName: "xmark.circle.fill").font(.system(size: 18, weight: .semibold))
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(.secondary)
                }
                .padding(.bottom, 4)

                Picker("", selection: $tab) {
                    Text("Projects").tag(0)
                    Text("User Profile").tag(1)
                    Text("System").tag(2)
                }
                .pickerStyle(.segmented)

                Group {
                    if tab == 0 { ProjectsSettingsView(vm: vm) }
                    if tab == 1 { UserSettingsView(vm: vm) }
                    if tab == 2 { SystemSettingsView(vm: vm) }
                }
                .background(.ultraThinMaterial)
                .cornerRadius(14)
                .overlay(RoundedRectangle(cornerRadius: 14).stroke(.white.opacity(0.08), lineWidth: 1))
                .shadow(color: .black.opacity(0.2), radius: 8, x: 0, y: 6)

                if let err = vm.errorMessage, !err.isEmpty {
                    Text(err).foregroundStyle(.red)
                } else if let banner = vm.savedBanner {
                    Text(banner).foregroundStyle(.green).transition(.opacity)
                }
            }
            .padding(20)
        }
        .onAppear { vm.loadAll() }
    }
}

struct ProjectsSettingsView: View {
    @ObservedObject var vm: SettingsViewModel

    var body: some View {
        VStack(alignment: .leading) {
            HStack {
                Button {
                    vm.projects.append(ProjectConfig(name: "New Project", description: "", agentEnabled: true))
                } label: {
                    Label("Add Project", systemImage: "plus")
                }
                .buttonStyle(.borderedProminent)
                Spacer()
                Button {
                    vm.saveProjects()
                } label: {
                    Label("Save", systemImage: "square.and.arrow.down")
                }
                .buttonStyle(.bordered)
            }
            .padding()

            ScrollView {
                VStack(spacing: 12) {
                    ForEach(Array(vm.projects.enumerated()), id: \.element.id) { index, _ in
                        ProjectRowEditor(
                            project: $vm.projects[index],
                            onDelete: { vm.projects.remove(at: index) }
                        )
                    }
                }
                .padding(12)
            }
        }
    }
}

struct ProjectRowEditor: View {
    @Binding var project: ProjectConfig
    var onDelete: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Project")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(.secondary)
                TextField("Name", text: $project.name)
                    .textFieldStyle(.roundedBorder)
            }
            VStack(alignment: .leading, spacing: 4) {
                Text("Description")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(.secondary)
                TextEditor(text: $project.description)
                    .frame(minHeight: 80)
                    .overlay(
                        RoundedRectangle(cornerRadius: 6)
                            .stroke(Color.white.opacity(0.15), lineWidth: 1)
                    )
            }
            Toggle(isOn: $project.agentEnabled) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Background agents enabled")
                        .font(.system(size: 12, weight: .semibold))
                    Text("Allow autonomous background tasks for this project.")
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                }
            }
            .toggleStyle(.switch)
            HStack {
                Spacer()
                Button(role: .destructive) {
                    onDelete()
                } label: {
                    Label("Remove", systemImage: "trash")
                }
            }
        }
        .padding(12)
        .background(Color.white.opacity(0.05))
        .cornerRadius(10)
    }
}

struct UserSettingsView: View {
    @ObservedObject var vm: SettingsViewModel
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Spacer()
                Button {
                    vm.saveUser()
                } label: {
                    Label("Save", systemImage: "square.and.arrow.down")
                }
                .buttonStyle(.bordered)
            }
            .padding(12)
            Form {
                TextField("Name", text: $vm.user.name)
                VStack(alignment: .leading) {
                    Text("Description")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundStyle(.secondary)
                    TextEditor(text: $vm.user.description)
                        .frame(minHeight: 100)
                }
                VStack(alignment: .leading) {
                    Text("Agent Goals")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundStyle(.secondary)
                    TextEditor(text: $vm.user.agentGoals)
                        .frame(minHeight: 100)
                }
            }
            .formStyle(.grouped)
            .padding(12)
        }
    }
}

struct SystemSettingsView: View {
    @ObservedObject var vm: SettingsViewModel
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Spacer()
                Button {
                    vm.saveSettings()
                } label: {
                    Label("Save", systemImage: "square.and.arrow.down")
                }
                .buttonStyle(.bordered)
            }
            .padding(12)

            VStack(alignment: .leading, spacing: 16) {
                GroupBox("Weights (0.0–5.0)") {
                    HStack {
                        Text("Value").frame(width: 160, alignment: .leading)
                        Slider(value: $vm.settings.valueWeight, in: 0.0...5.0, step: 0.1)
                        Text(String(format: "%.2f", vm.settings.valueWeight)).frame(width: 60, alignment: .trailing)
                    }
                    HStack {
                        Text("Feasibility").frame(width: 160, alignment: .leading)
                        Slider(value: $vm.settings.feasibilityWeight, in: 0.0...5.0, step: 0.1)
                        Text(String(format: "%.2f", vm.settings.feasibilityWeight)).frame(width: 60, alignment: .trailing)
                    }
                    HStack {
                        Text("Preference Alignment").frame(width: 160, alignment: .leading)
                        Slider(value: $vm.settings.userPreferenceAlignmentWeight, in: 0.0...5.0, step: 0.1)
                        Text(String(format: "%.2f", vm.settings.userPreferenceAlignmentWeight)).frame(width: 60, alignment: .trailing)
                    }
                }
                GroupBox("Deployment") {
                    HStack {
                        Text("Max Deployed Tasks").frame(width: 160, alignment: .leading)
                        TextField("", value: $vm.settings.maxDeployedTasks, formatter: NumberFormatter.integer)
                            .textFieldStyle(.roundedBorder)
                            .frame(width: 80)
                    }
                    HStack {
                        Text("Deployment Threshold").frame(width: 160, alignment: .leading)
                        Slider(value: $vm.settings.deploymentThreshold, in: 0.0...1.0, step: 0.01)
                        Text(String(format: "%.2f", vm.settings.deploymentThreshold)).frame(width: 60, alignment: .trailing)
                    }
                    HStack {
                        Text("Safety Threshold").frame(width: 160, alignment: .leading)
                        Slider(value: Binding(
                            get: { Double(vm.settings.safetyThreshold) },
                            set: { vm.settings.safetyThreshold = Int($0.rounded()) }
                        ), in: 1...10, step: 1)
                        Text("\(vm.settings.safetyThreshold)").frame(width: 60, alignment: .trailing)
                    }
                }
                GroupBox("Notifications & Agent Sensitivity") {
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Departure (when leaving a project)").font(.system(size: 12, weight: .semibold))
                        HStack {
                            Text("Min Entries in Previous Segment").frame(width: 220, alignment: .leading)
                            TextField("", value: $vm.settings.departureMinEntriesPreviousSegment, formatter: NumberFormatter.integer)
                                .textFieldStyle(.roundedBorder)
                                .frame(width: 80)
                            Spacer()
                        }
                        HStack {
                            Text("Time Threshold (minutes)").frame(width: 220, alignment: .leading)
                            Slider(value: $vm.settings.departureTimeThresholdMinutes, in: 0...120, step: 1)
                            Text(String(format: "%.0f", vm.settings.departureTimeThresholdMinutes)).frame(width: 60, alignment: .trailing)
                        }
                        Divider().padding(.vertical, 4)
                        Text("Arrival (when returning to a project)").font(.system(size: 12, weight: .semibold))
                        HStack {
                            Text("Min Entries in Current Segment").frame(width: 220, alignment: .leading)
                            TextField("", value: $vm.settings.arrivalMinEntriesCurrentSegment, formatter: NumberFormatter.integer)
                                .textFieldStyle(.roundedBorder)
                                .frame(width: 80)
                            Spacer()
                        }
                        HStack {
                            Text("Absence Threshold (minutes)").frame(width: 220, alignment: .leading)
                            Slider(value: $vm.settings.arrivalTimeThresholdMinutes, in: 0...240, step: 1)
                            Text(String(format: "%.0f", vm.settings.arrivalTimeThresholdMinutes)).frame(width: 60, alignment: .trailing)
                        }
                        Divider().padding(.vertical, 4)
                        Text("Observation Cooldown (Gum)").font(.system(size: 12, weight: .semibold))
                        HStack {
                            Text("Cooldown (seconds)").frame(width: 220, alignment: .leading)
                            Slider(value: $vm.settings.observationCooldownSeconds, in: 0...600, step: 5)
                            Text(String(format: "%.0f", vm.settings.observationCooldownSeconds)).frame(width: 60, alignment: .trailing)
                        }
                    }
                }
            }
            .padding(12)
        }
    }
}

private extension NumberFormatter {
    static var integer: NumberFormatter {
        let nf = NumberFormatter()
        nf.numberStyle = .none
        nf.maximumFractionDigits = 0
        return nf
    }
}



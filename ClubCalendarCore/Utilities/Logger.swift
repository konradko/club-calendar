import Foundation
import OSLog
import os
#if canImport(AppKit)
import AppKit
#endif

extension Logger {
    public static let subsystem = "com.clubcalendar.app"

    public static let sync = Logger(subsystem: subsystem, category: "sync")
    public static let strava = Logger(subsystem: subsystem, category: "strava")
    public static let auth = Logger(subsystem: subsystem, category: "auth")
    public static let calendar = Logger(subsystem: subsystem, category: "calendar")
    public static let app = Logger(subsystem: subsystem, category: "app")
}

/// Reads recent entries from the unified log and exports them to a temp file.
/// On macOS, opens the dump in the user's default text editor (or falls back
/// to Console.app). On iOS the dump file is left at `temporaryDirectory` for
/// programmatic export — the caller decides how to share it.
public enum LogViewer {
    private static let dumpFile = FileManager.default.temporaryDirectory
        .appendingPathComponent("club-calendar.log")

    /// The path the most recent dump was written to.
    public static var dumpFileURL: URL { dumpFile }

    /// Writes recent log entries to `dumpFileURL` and returns the URL.
    @MainActor
    @discardableResult
    public static func exportRecentLogs(hours: Int = 24) -> URL? {
        do {
            let store = try OSLogStore(scope: .currentProcessIdentifier)
            let since = store.position(date: Date().addingTimeInterval(-Double(hours) * 3600))
            let predicate = NSPredicate(format: "subsystem == %@", Logger.subsystem)
            let entries = try store.getEntries(at: since, matching: predicate)

            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]

            var lines: [String] = []
            for entry in entries {
                guard let log = entry as? OSLogEntryLog else { continue }
                lines.append("\(formatter.string(from: log.date)) [\(log.level.label)] [\(log.category)] \(log.composedMessage)")
            }

            let text = lines.isEmpty
                ? "No log entries in the last \(hours) hours.\n"
                : lines.joined(separator: "\n") + "\n"

            try text.write(to: dumpFile, atomically: true, encoding: .utf8)
            return dumpFile
        } catch {
            Logger.app.error("Failed to export logs: \(error.localizedDescription, privacy: .public)")
            return nil
        }
    }

    #if canImport(AppKit)
    /// Exports recent logs and opens them in the user's default editor.
    /// Falls back to Console.app if opening the dump fails.
    @MainActor
    public static func openRecentLogs(hours: Int = 24) {
        if let url = exportRecentLogs(hours: hours) {
            NSWorkspace.shared.open(url)
            return
        }
        if let consoleURL = NSWorkspace.shared.urlForApplication(
            withBundleIdentifier: "com.apple.Console"
        ) {
            NSWorkspace.shared.open(consoleURL)
        }
    }
    #endif
}

private extension OSLogEntryLog.Level {
    var label: String {
        switch self {
        case .undefined: return "UNDEFINED"
        case .debug: return "DEBUG"
        case .info: return "INFO"
        case .notice: return "NOTICE"
        case .error: return "ERROR"
        case .fault: return "FAULT"
        @unknown default: return "UNKNOWN"
        }
    }
}

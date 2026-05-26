import AppKit
import Foundation
import OSLog
import os

extension Logger {
    static let subsystem = "com.clubcalendar.app"

    static let sync = Logger(subsystem: subsystem, category: "sync")
    static let strava = Logger(subsystem: subsystem, category: "strava")
    static let auth = Logger(subsystem: subsystem, category: "auth")
    static let calendar = Logger(subsystem: subsystem, category: "calendar")
    static let app = Logger(subsystem: subsystem, category: "app")
}

/// Reads recent entries from the unified log and opens them in the default text
/// editor. Replaces the older parallel file-log: os.Logger already persists
/// across launches, so we just dump on demand.
enum LogViewer {
    private static let dumpFile = FileManager.default.temporaryDirectory
        .appendingPathComponent("club-calendar.log")

    @MainActor
    static func openRecentLogs(hours: Int = 24) {
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
            NSWorkspace.shared.open(dumpFile)
        } catch {
            Logger.app.error("Failed to export logs: \(error.localizedDescription, privacy: .public)")
            // Fall back to opening Console.app so the user has somewhere to look.
            if let consoleURL = NSWorkspace.shared.urlForApplication(
                withBundleIdentifier: "com.apple.Console"
            ) {
                NSWorkspace.shared.open(consoleURL)
            }
        }
    }
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

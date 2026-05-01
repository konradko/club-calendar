import AppKit
import Foundation
import os

extension Logger {
    static let subsystem = "com.clubcalendar.app"

    static let sync = Logger(subsystem: subsystem, category: "sync")
    static let strava = Logger(subsystem: subsystem, category: "strava")
    static let auth = Logger(subsystem: subsystem, category: "auth")
    static let calendar = Logger(subsystem: subsystem, category: "calendar")
    static let app = Logger(subsystem: subsystem, category: "app")
}

/// Appends log lines to a file for post-mortem debugging.
enum FileLog {
    static let logDirectory = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Library/Logs/Club Calendar")

    static let logFile = logDirectory.appendingPathComponent("club-calendar-swift.log")

    private static let queue = DispatchQueue(label: "com.clubcalendar.filelog", qos: .utility)

    private static let dateFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd HH:mm:ss"
        formatter.locale = Locale(identifier: "en_US_POSIX")
        return formatter
    }()

    /// Writes a log line to the file. Non-blocking (dispatched to background queue).
    static func write(_ message: String, level: String = "INFO", category: String = "app") {
        queue.async {
            do {
                try FileManager.default.createDirectory(at: logDirectory, withIntermediateDirectories: true)

                let timestamp = dateFormatter.string(from: Date())
                let line = "\(timestamp) [\(level)] [\(category)] \(message)\n"

                if FileManager.default.fileExists(atPath: logFile.path) {
                    let handle = try FileHandle(forWritingTo: logFile)
                    handle.seekToEndOfFile()
                    handle.write(Data(line.utf8))
                    handle.closeFile()
                } else {
                    try Data(line.utf8).write(to: logFile)
                }
            } catch {
                // Last resort — can't log a logging failure
            }
        }
    }

    /// Returns the path to the log file, creating the directory if needed.
    static var logFilePath: String {
        logFile.path
    }

    /// Opens the log file in the default text editor.
    @MainActor
    static func openLogFile() {
        // Create file if it doesn't exist so the user sees something
        if !FileManager.default.fileExists(atPath: logFile.path) {
            try? FileManager.default.createDirectory(at: logDirectory, withIntermediateDirectories: true)
            FileManager.default.createFile(atPath: logFile.path, contents: nil)
        }
        NSWorkspace.shared.open(logFile)
    }
}

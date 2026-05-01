import SwiftUI
import os

struct MenuBarView: View {
    @Environment(AppState.self) private var appState
    @Environment(\.openSettings) private var openSettings

    var body: some View {
        // Drop events whose start has already passed so a stale cache
        // (e.g. when auto-sync hasn't run for a while because the Mac was
        // asleep) doesn't surface yesterday's rides in the menu.
        let now = Date()
        let upcoming = appState.upcomingEvents.filter { $0.startDate >= now }

        Group {
            // Warning banner if needed
            if let warning = warningMessage {
                Text(warning)
                    .foregroundStyle(.secondary)
                Divider()
            }

            // Upcoming events
            if appState.settings.showUpcomingEvents && !upcoming.isEmpty {
                eventsSection(upcoming)
                Divider()
            }

            // Sync status
            syncStatusSection
            Divider()

            // Actions
            Button("Settings...") {
                NSApplication.shared.activate(ignoringOtherApps: true)
                openSettings()
            }
            .keyboardShortcut(",", modifiers: .command)

            Button("View Logs...") {
                FileLog.openLogFile()
            }

            Button("Quit Club Calendar") {
                NSApplication.shared.terminate(nil)
            }
            .keyboardShortcut("q", modifiers: .command)
        }
        .task {
            await appState.onAppear()
        }
    }

    // MARK: - Warning Banner

    private var warningMessage: String? {
        if appState.calendarAccessStatus != .authorized {
            return "⚠️ Calendar access required"
        }
        if !appState.isAuthenticated {
            return "⚠️ Not connected to Strava"
        }
        return nil
    }

    // MARK: - Events Section

    @ViewBuilder
    private func eventsSection(_ events: [UpcomingEvent]) -> some View {
        let groupedEvents = groupEventsByDay(events)

        ForEach(groupedEvents, id: \.date) { group in
            Text(formatDayHeader(group.date))
                .font(.caption)
                .foregroundStyle(.secondary)

            ForEach(group.events) { event in
                EventRow(event: event)
            }
        }
    }

    // MARK: - Sync Status

    @ViewBuilder
    private var syncStatusSection: some View {
        if let lastSync = appState.syncService.lastSyncTimeFormatted {
            Text("Last synced: \(lastSync)")
                .font(.caption)
                .foregroundStyle(.secondary)
        }

        Button {
            Task {
                await appState.sync()
            }
        } label: {
            if appState.syncService.syncInProgress {
                Text("Syncing...")
            } else {
                Text("↻ Sync Now")
            }
        }
        .disabled(appState.syncService.syncInProgress)
    }

    // MARK: - Helpers

    private struct DayGroup {
        let date: Date
        let events: [UpcomingEvent]
    }

    private func groupEventsByDay(_ events: [UpcomingEvent]) -> [DayGroup] {
        let calendar = Calendar.current
        var groups: [Date: [UpcomingEvent]] = [:]

        for event in events {
            let dayStart = calendar.startOfDay(for: event.startDate)
            groups[dayStart, default: []].append(event)
        }

        return groups.keys.sorted().map { date in
            DayGroup(date: date, events: groups[date]!)
        }
    }

    private func formatDayHeader(_ date: Date) -> String {
        let calendar = Calendar.current

        if calendar.isDateInToday(date) {
            return "Today"
        } else if calendar.isDateInTomorrow(date) {
            return "Tomorrow"
        } else {
            let formatter = DateFormatter()
            formatter.dateFormat = "EEE, d MMM"
            return formatter.string(from: date)
        }
    }
}

// MARK: - Event Row

struct EventRow: View {
    let event: UpcomingEvent

    var body: some View {
        Button("\(timeString)  \(event.title)") {
            openInCalendar()
        }
    }

    private var timeString: String {
        let formatter = DateFormatter()
        formatter.timeStyle = .short
        return formatter.string(from: event.startDate)
    }

    private func openInCalendar() {
        NSWorkspace.shared.open(URL(fileURLWithPath: "/System/Applications/Calendar.app"))
    }
}

import SwiftUI
import ClubCalendarCore

struct TodayView: View {
    @Environment(AppState.self) private var appState

    var body: some View {
        NavigationStack {
            content
                .navigationTitle("Today")
                .toolbar {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button {
                            Task { await appState.sync() }
                        } label: {
                            if appState.syncService.syncInProgress {
                                ProgressView()
                            } else {
                                Image(systemName: "arrow.clockwise")
                            }
                        }
                        .disabled(appState.syncService.syncInProgress)
                    }
                }
        }
    }

    @ViewBuilder
    private var content: some View {
        if !appState.isAuthenticated {
            ContentUnavailableView(
                "Not connected",
                systemImage: "person.crop.circle.badge.exclamationmark",
                description: Text("Connect to Strava in Settings to start syncing club events.")
            )
        } else if appState.calendarAccessStatus != .authorized {
            ContentUnavailableView(
                "Calendar access required",
                systemImage: "calendar.badge.exclamationmark",
                description: Text("Grant calendar access in Settings so Club Calendar can write events.")
            )
        } else if upcomingEvents.isEmpty {
            ContentUnavailableView(
                "No upcoming events",
                systemImage: "calendar",
                description: Text(syncStatusDescription)
            )
            .refreshable { await appState.sync() }
        } else {
            List {
                ForEach(groupedDays, id: \.0) { day, events in
                    Section(dayHeader(day)) {
                        ForEach(events) { event in
                            EventRow(event: event)
                        }
                    }
                }
                if let last = appState.syncService.lastSyncTimeFormatted {
                    Section {
                        Text("Last synced \(last)")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .refreshable { await appState.sync() }
        }
    }

    // MARK: - Derived state

    private var upcomingEvents: [CalendarEventData] {
        appState.upcomingEvents.filter { $0.startDate >= Date() }
    }

    private var groupedDays: [(Date, [CalendarEventData])] {
        let calendar = Calendar.current
        let grouped = Dictionary(grouping: upcomingEvents) { event in
            calendar.startOfDay(for: event.startDate)
        }
        return grouped
            .map { ($0.key, $0.value.sorted { $0.startDate < $1.startDate }) }
            .sorted { $0.0 < $1.0 }
    }

    private func dayHeader(_ date: Date) -> String {
        let calendar = Calendar.current
        if calendar.isDateInToday(date) { return "Today" }
        if calendar.isDateInTomorrow(date) { return "Tomorrow" }
        return date.formatted(.dateTime.weekday(.wide).month().day())
    }

    private var syncStatusDescription: String {
        if let error = appState.syncService.lastSyncError {
            return "Last sync failed: \(error.localizedDescription)"
        }
        if let last = appState.syncService.lastSyncTimeFormatted {
            return "Pull to refresh. Last synced \(last)."
        }
        return "Pull to refresh."
    }
}

private struct EventRow: View {
    @Environment(\.openURL) private var openURL
    let event: CalendarEventData

    var body: some View {
        Button {
            if let url = event.url { openURL(url) }
        } label: {
            VStack(alignment: .leading, spacing: 4) {
                Text(event.title)
                    .font(.body)
                    .lineLimit(2)
                Text(event.startDate.formatted(date: .omitted, time: .shortened))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.vertical, 2)
            .contentShape(.rect)
        }
        .buttonStyle(.plain)
        .disabled(event.url == nil)
    }
}

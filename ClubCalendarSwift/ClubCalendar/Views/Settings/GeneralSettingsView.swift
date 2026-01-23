import SwiftUI
import EventKit

struct GeneralSettingsView: View {
    @Environment(AppState.self) private var appState

    var body: some View {
        @Bindable var settings = appState.settings

        Form {
            // Calendar Access
            Section {
                HStack {
                    Label {
                        Text("Calendar Access")
                    } icon: {
                        Image(systemName: calendarStatusIcon)
                            .foregroundStyle(calendarStatusColor)
                    }

                    Spacer()

                    Text(calendarStatusText)
                        .foregroundStyle(.secondary)
                }

                if appState.calendarAccessStatus == .notDetermined {
                    Button("Request Access") {
                        Task {
                            await appState.requestCalendarAccess()
                        }
                    }
                } else if appState.calendarAccessStatus == .denied {
                    Button("Open System Settings") {
                        if let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Calendars") {
                            NSWorkspace.shared.open(url)
                        }
                    }
                }
            }

            // Sync Settings
            Section {
                Picker("Sync Interval", selection: $settings.syncInterval) {
                    ForEach(SyncInterval.allCases) { interval in
                        Text(interval.displayName).tag(interval)
                    }
                }
                .onChange(of: settings.syncInterval) {
                    appState.syncService.restartAutoSync()
                }

                Picker("Calendar", selection: $settings.calendarName) {
                    ForEach(availableCalendars, id: \.title) { calendar in
                        Text(calendar.title).tag(calendar.title)
                    }
                }
            }

            // Display Settings
            Section {
                Toggle("Start at login", isOn: Binding(
                    get: { appState.isLoginItemEnabled },
                    set: { appState.setLoginItemEnabled($0) }
                ))

                Toggle("Show upcoming events in menu", isOn: $settings.showUpcomingEvents)

                if settings.showUpcomingEvents {
                    Picker("Max events in menu", selection: $settings.maxMenuEvents) {
                        ForEach([5, 10, 15, 20, 25], id: \.self) { count in
                            Text("\(count)").tag(count)
                        }
                    }
                }
            }
        }
        .formStyle(.grouped)
        .padding()
    }

    private var availableCalendars: [EKCalendar] {
        // Return available calendars from CalendarService
        // For now, return empty and let the user type
        []
    }

    private var calendarStatusIcon: String {
        switch appState.calendarAccessStatus {
        case .authorized: return "checkmark.circle.fill"
        case .denied: return "xmark.circle.fill"
        case .restricted: return "exclamationmark.triangle.fill"
        case .notDetermined: return "questionmark.circle.fill"
        }
    }

    private var calendarStatusColor: Color {
        switch appState.calendarAccessStatus {
        case .authorized: return .green
        case .denied: return .red
        case .restricted: return .orange
        case .notDetermined: return .secondary
        }
    }

    private var calendarStatusText: String {
        switch appState.calendarAccessStatus {
        case .authorized: return "Granted"
        case .denied: return "Denied"
        case .restricted: return "Restricted"
        case .notDetermined: return "Not requested"
        }
    }
}

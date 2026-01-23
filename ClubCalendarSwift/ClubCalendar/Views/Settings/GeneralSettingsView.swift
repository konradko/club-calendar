import SwiftUI
import EventKit

struct GeneralSettingsView: View {
    @Environment(AppState.self) private var appState

    var body: some View {
        @Bindable var settings = appState.settings

        Form {
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
}

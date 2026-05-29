import SwiftUI
import ClubCalendarCore

struct SettingsView: View {
    @Environment(AppState.self) private var appState

    var body: some View {
        @Bindable var settings = appState.settings

        NavigationStack {
            Form {
                accountSection

                Section("Sync") {
                    Picker("Interval", selection: $settings.syncInterval) {
                        ForEach(SyncInterval.allCases) { interval in
                            Text(interval.displayName).tag(interval)
                        }
                    }
                }

                Section("Appearance") {
                    Picker("Theme", selection: $settings.appearanceMode) {
                        ForEach(AppearanceMode.allCases) { mode in
                            Text(mode.displayName).tag(mode)
                        }
                    }
                    .pickerStyle(.segmented)
                }

                Section("Calendar") {
                    HStack {
                        Text("Access")
                        Spacer()
                        Text(calendarStatusText)
                            .foregroundStyle(calendarStatusColor)
                    }
                    if appState.calendarAccessStatus != .authorized {
                        Button("Grant calendar access") {
                            Task { await appState.requestCalendarAccess() }
                        }
                    }
                }

                Section("Status") {
                    if let lastSync = appState.syncService.lastSyncTimeFormatted {
                        HStack {
                            Text("Last synced")
                            Spacer()
                            Text(lastSync).foregroundStyle(.secondary)
                        }
                    }
                    if let error = appState.syncService.lastSyncError {
                        Text(error.localizedDescription)
                            .font(.footnote)
                            .foregroundStyle(.red)
                    }
                    Button("Sync now") {
                        Task { await appState.sync() }
                    }
                    .disabled(appState.syncService.syncInProgress)
                }

                Section("Diagnostics") {
                    LogExportRow()
                }
            }
            .navigationTitle("Settings")
        }
    }

    @ViewBuilder
    private var accountSection: some View {
        Section("Strava") {
            if appState.isAuthenticated {
                HStack {
                    Text("Signed in as")
                    Spacer()
                    Text(appState.athleteName ?? "—")
                        .foregroundStyle(.secondary)
                }
                Button("Disconnect", role: .destructive) {
                    Task { await appState.disconnect() }
                }
            } else {
                Button("Connect to Strava") {
                    Task { await appState.authenticate() }
                }
                .disabled(!appState.hasAPICredentials || appState.isLoading)
                if !appState.hasAPICredentials {
                    Text("Add your Strava API credentials in onboarding before connecting.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
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

    private var calendarStatusColor: Color {
        switch appState.calendarAccessStatus {
        case .authorized: return .green
        case .denied, .restricted: return .red
        case .notDetermined: return .secondary
        }
    }
}

/// Exports recent unified-log entries to a temp file and surfaces a ShareLink
/// so the user can email/AirDrop them to themselves for debugging. Parity
/// with the macOS app's "View Logs" menu item.
struct LogExportRow: View {
    @State private var exportedURL: URL?
    @State private var isExporting = false

    var body: some View {
        Group {
            if let url = exportedURL {
                ShareLink("Share logs", item: url)
            } else {
                Button {
                    isExporting = true
                    Task { @MainActor in
                        exportedURL = LogViewer.exportRecentLogs(hours: 24)
                        isExporting = false
                    }
                } label: {
                    if isExporting {
                        ProgressView()
                    } else {
                        Text("Export last 24h of logs")
                    }
                }
                .disabled(isExporting)
            }
        }
    }
}

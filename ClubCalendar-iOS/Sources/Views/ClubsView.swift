import SwiftUI
import ClubCalendarCore

struct ClubsView: View {
    @Environment(AppState.self) private var appState

    var body: some View {
        NavigationStack {
            content
                .navigationTitle("Clubs")
                .toolbar {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button {
                            Task { await appState.refreshClubs() }
                        } label: {
                            if appState.isLoading {
                                ProgressView()
                            } else {
                                Image(systemName: "arrow.clockwise")
                            }
                        }
                        .disabled(appState.isLoading)
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
                description: Text("Connect to Strava in Settings before picking clubs.")
            )
        } else if appState.settings.syncableClubs.isEmpty {
            ContentUnavailableView {
                Label("No clubs yet", systemImage: "person.3")
            } description: {
                Text("Tap refresh to fetch the clubs you've joined on Strava.")
            } actions: {
                Button("Refresh") {
                    Task { await appState.refreshClubs() }
                }
                .disabled(appState.isLoading)
            }
        } else {
            List {
                Section {
                    ForEach(appState.settings.syncableClubs) { syncable in
                        ClubToggleRow(
                            syncable: syncable,
                            onToggle: { enabled in
                                appState.settings.setClubEnabled(syncable.id, enabled: enabled)
                            }
                        )
                    }
                } footer: {
                    Text("Disabled clubs stop receiving new events; existing future events are marked [CANCELLED] on the next sync.")
                }
            }
            .refreshable { await appState.refreshClubs() }
        }
    }
}

private struct ClubToggleRow: View {
    let syncable: SyncableClub
    let onToggle: (Bool) -> Void

    var body: some View {
        Toggle(isOn: Binding(
            get: { syncable.isEnabled },
            set: { onToggle($0) }
        )) {
            VStack(alignment: .leading, spacing: 2) {
                Text(syncable.club.name)
                if let city = syncable.club.city {
                    Text(city)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
        }
    }
}

import SwiftUI
import ClubCalendarCore

struct ClubsSettingsView: View {
    @Environment(AppState.self) private var appState

    var body: some View {
        VStack(spacing: 0) {
            if appState.settings.syncableClubs.isEmpty {
                emptyState
            } else {
                clubsList
            }

            Divider()

            // Refresh button
            HStack {
                Spacer()
                Button {
                    Task {
                        await appState.refreshClubs()
                    }
                } label: {
                    HStack(spacing: 4) {
                        if appState.isLoading {
                            ProgressView()
                                .scaleEffect(0.6)
                        } else {
                            Image(systemName: "arrow.clockwise")
                        }
                        Text("Refresh clubs")
                    }
                }
                .disabled(appState.isLoading || !appState.isAuthenticated)
            }
            .padding()
        }
    }

    private var emptyState: some View {
        VStack(spacing: 12) {
            if !appState.isAuthenticated {
                Image(systemName: "person.crop.circle.badge.exclamationmark")
                    .font(.system(size: 40))
                    .foregroundStyle(.secondary)

                Text("Connect to Strava first")
                    .font(.headline)

                Text("Go to the Account tab to connect your Strava account.")
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            } else if appState.isLoading {
                ProgressView()
                Text("Loading clubs...")
                    .font(.callout)
                    .foregroundStyle(.secondary)
            } else {
                Image(systemName: "person.3")
                    .font(.system(size: 40))
                    .foregroundStyle(.secondary)

                Text("No clubs found")
                    .font(.headline)

                Text("You don't appear to be a member of any Strava clubs.")
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding()
    }

    private var clubsList: some View {
        List {
            ForEach(appState.settings.syncableClubs) { syncable in
                ClubSettingsRow(syncableClub: syncable) { enabled in
                    appState.settings.setClubEnabled(syncable.id, enabled: enabled)
                }
            }
        }
        .listStyle(.bordered(alternatesRowBackgrounds: true))
    }
}

struct ClubSettingsRow: View {
    let syncableClub: SyncableClub
    let onToggle: (Bool) -> Void

    var body: some View {
        Toggle(isOn: Binding(
            get: { syncableClub.isEnabled },
            set: { onToggle($0) }
        )) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(syncableClub.club.name)
                        .font(.body)

                    HStack(spacing: 8) {
                        if let city = syncableClub.club.city {
                            Label(city, systemImage: "mappin")
                        }
                        Label("\(syncableClub.club.memberCount) members", systemImage: "person.2")
                    }
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .labelStyle(.titleOnly)
                }

                Spacer()

                if let sportType = syncableClub.club.sportType {
                    Text(sportEmoji(for: sportType))
                        .font(.title2)
                }
            }
        }
        .toggleStyle(.checkbox)
        .padding(.vertical, 2)
    }

    private func sportEmoji(for sportType: String) -> String {
        switch sportType.lowercased() {
        case "cycling": return "🚴"
        case "running": return "🏃"
        case "triathlon": return "🏊"
        default: return "📅"
        }
    }
}

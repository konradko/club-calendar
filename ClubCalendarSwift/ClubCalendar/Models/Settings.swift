import Foundation
import SwiftUI

/// Sync interval options in minutes.
enum SyncInterval: Int, CaseIterable, Identifiable, Sendable {
    case fifteenMinutes = 15
    case thirtyMinutes = 30
    case oneHour = 60
    case twoHours = 120
    case never = 0

    var id: Int { rawValue }

    var displayName: String {
        switch self {
        case .fifteenMinutes: return "Every 15 minutes"
        case .thirtyMinutes: return "Every 30 minutes"
        case .oneHour: return "Every hour"
        case .twoHours: return "Every 2 hours"
        case .never: return "Never"
        }
    }
}

/// Observable settings manager using @AppStorage.
@MainActor
@Observable
final class AppSettings {
    static let shared = AppSettings()

    /// Sync interval in minutes (0 = never).
    @ObservationIgnored
    @AppStorage("syncIntervalMinutes") var syncIntervalMinutes: Int = 60

    /// Name of the calendar to sync events to.
    @ObservationIgnored
    @AppStorage("calendarName") var calendarName: String = "Club Calendar"

    /// Whether to start the app at login.
    @ObservationIgnored
    @AppStorage("startAtLogin") var startAtLogin: Bool = false

    /// Whether to show upcoming events in the menu bar.
    @ObservationIgnored
    @AppStorage("showUpcomingEvents") var showUpcomingEvents: Bool = true

    /// Maximum number of events to show in the menu.
    @ObservationIgnored
    @AppStorage("maxMenuEvents") var maxMenuEvents: Int = 15

    /// Whether onboarding has been completed.
    @ObservationIgnored
    @AppStorage("onboardingCompleted") var onboardingCompleted: Bool = false

    private static let syncableClubsKey = "syncableClubsData"

    /// The clubs available for syncing with their enabled state.
    var syncableClubs: [SyncableClub] {
        didSet { persistSyncableClubs() }
    }

    var syncInterval: SyncInterval {
        get { SyncInterval(rawValue: syncIntervalMinutes) ?? .oneHour }
        set { syncIntervalMinutes = newValue.rawValue }
    }

    /// IDs of clubs that are enabled for syncing.
    var enabledClubIds: Set<Int> {
        Set(syncableClubs.filter(\.isEnabled).map(\.id))
    }

    /// Updates the clubs list with new clubs from Strava, preserving enabled state.
    func updateClubs(_ clubs: [Club]) {
        let existingStates = Dictionary(uniqueKeysWithValues: syncableClubs.map { ($0.id, $0.isEnabled) })
        syncableClubs = clubs.map { club in
            SyncableClub(club: club, isEnabled: existingStates[club.id] ?? true)
        }
    }

    /// Sets the enabled state for a specific club.
    func setClubEnabled(_ clubId: Int, enabled: Bool) {
        if let index = syncableClubs.firstIndex(where: { $0.id == clubId }) {
            syncableClubs[index].isEnabled = enabled
        }
    }

    private func persistSyncableClubs() {
        let data = (try? JSONEncoder().encode(syncableClubs)) ?? Data()
        UserDefaults.standard.set(data, forKey: Self.syncableClubsKey)
    }

    private init() {
        if let data = UserDefaults.standard.data(forKey: Self.syncableClubsKey),
           let clubs = try? JSONDecoder().decode([SyncableClub].self, from: data) {
            self.syncableClubs = clubs
        } else {
            self.syncableClubs = []
        }
    }
}

import Foundation
import SwiftUI

/// Sync interval options in minutes.
public enum SyncInterval: Int, CaseIterable, Identifiable, Sendable {
    case fifteenMinutes = 15
    case thirtyMinutes = 30
    case oneHour = 60
    case twoHours = 120
    case never = 0

    public var id: Int { rawValue }

    public var displayName: String {
        switch self {
        case .fifteenMinutes: return "Every 15 minutes"
        case .thirtyMinutes: return "Every 30 minutes"
        case .oneHour: return "Every hour"
        case .twoHours: return "Every 2 hours"
        case .never: return "Never"
        }
    }
}

/// App appearance options. `system` defers to the device light/dark setting.
public enum AppearanceMode: String, CaseIterable, Identifiable, Sendable {
    case system
    case light
    case dark

    public var id: String { rawValue }

    public var displayName: String {
        switch self {
        case .system: return "System"
        case .light: return "Light"
        case .dark: return "Dark"
        }
    }

    /// The `ColorScheme` to force, or `nil` to follow the system.
    public var colorScheme: ColorScheme? {
        switch self {
        case .system: return nil
        case .light: return .light
        case .dark: return .dark
        }
    }
}

/// Observable settings manager using @AppStorage.
@MainActor
@Observable
public final class AppSettings {
    public static let shared = AppSettings()

    /// Sync interval in minutes (0 = never).
    @ObservationIgnored
    @AppStorage("syncIntervalMinutes") public var syncIntervalMinutes: Int = 60

    /// Name of the calendar to sync events to.
    @ObservationIgnored
    @AppStorage("calendarName") public var calendarName: String = "Club Calendar"

    /// Whether to show upcoming events in the menu bar.
    @ObservationIgnored
    @AppStorage("showUpcomingEvents") public var showUpcomingEvents: Bool = true

    /// Maximum number of events to show in the menu.
    @ObservationIgnored
    @AppStorage("maxMenuEvents") public var maxMenuEvents: Int = 15

    /// Whether onboarding has been completed.
    @ObservationIgnored
    @AppStorage("onboardingCompleted") public var onboardingCompleted: Bool = false

    /// Preferred appearance (iOS). `.system` follows the device setting.
    @ObservationIgnored
    @AppStorage("appearanceMode") public var appearanceMode: AppearanceMode = .system

    private static let syncableClubsKey = "syncableClubsData"

    /// The clubs available for syncing with their enabled state.
    public var syncableClubs: [SyncableClub] {
        didSet { persistSyncableClubs() }
    }

    public var syncInterval: SyncInterval {
        get { SyncInterval(rawValue: syncIntervalMinutes) ?? .oneHour }
        set { syncIntervalMinutes = newValue.rawValue }
    }

    /// IDs of clubs that are enabled for syncing.
    public var enabledClubIds: Set<Int> {
        Set(syncableClubs.filter(\.isEnabled).map(\.id))
    }

    /// Updates the clubs list with new clubs from Strava, preserving enabled state.
    public func updateClubs(_ clubs: [Club]) {
        let existingStates = Dictionary(uniqueKeysWithValues: syncableClubs.map { ($0.id, $0.isEnabled) })
        syncableClubs = clubs.map { club in
            SyncableClub(club: club, isEnabled: existingStates[club.id] ?? true)
        }
    }

    /// Sets the enabled state for a specific club.
    public func setClubEnabled(_ clubId: Int, enabled: Bool) {
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

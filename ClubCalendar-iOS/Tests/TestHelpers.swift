import Foundation
import ClubCalendarCore
@testable import ClubCalendarIOS

/// Shared utilities for iOS test suites. Each suite typically wants a clean
/// keychain + clean settings, so it doesn't inherit state from another suite
/// that ran earlier in the same process.
@MainActor
enum TestHelpers {
    /// Builds a fresh AppState backed by an in-memory MockKeychainHelper.
    /// Use this in every iOS test — the simulator's real keychain isn't
    /// reliably accessible to unsigned test bundles, so all tests inject
    /// the mock.
    static func makeAppState() -> AppState {
        let keychain = MockKeychainHelper()
        resetSettings()
        return AppState(keychain: keychain, settings: AppSettings.shared)
    }

    /// Builds an AppState with a pre-populated mock keychain so tests can
    /// start from an "authenticated" state without driving OAuth.
    static func makeAuthedAppState(athleteName: String = "Alex") -> AppState {
        let keychain = MockKeychainHelper()
        try? keychain.save("test_client_id", for: .clientId)
        try? keychain.save("test_client_secret", for: .clientSecret)
        try? keychain.saveTokens(
            accessToken: "test_access",
            refreshToken: "test_refresh",
            expiresAt: Date().addingTimeInterval(3600)
        )
        try? keychain.save("12345", for: .athleteId)
        try? keychain.save(athleteName, for: .athleteName)
        resetSettings()
        return AppState(keychain: keychain, settings: AppSettings.shared)
    }

    /// Builds an AppState whose CalendarService points at a unique, never-
    /// created calendar, so `getUpcomingEvents` deterministically returns `[]`
    /// regardless of what the shared "Club Calendar" calendar on this simulator
    /// holds (a real sync from manual app use would otherwise leak in).
    static func makeAppStateWithEmptyCalendar() -> AppState {
        resetSettings()
        return AppState(
            keychain: MockKeychainHelper(),
            settings: AppSettings.shared,
            calendarService: CalendarService(calendarName: "ClubCalendarTests-Empty-\(UUID().uuidString)")
        )
    }

    /// Best-effort wipe of the real keychain — only matters if a test
    /// accidentally constructs `AppState()` (production init). Kept for
    /// belt-and-braces cleanup.
    static func wipeKeychain() {
        try? KeychainHelper.shared.clearAll()
    }

    /// Resets `AppSettings.shared` to the defaults the app ships with.
    /// `@AppStorage` keys are reset by removing their UserDefaults entries.
    static func resetSettings() {
        let defaults = UserDefaults.standard
        for key in [
            "syncIntervalMinutes", "calendarName", "showUpcomingEvents",
            "maxMenuEvents", "onboardingCompleted", "syncableClubsData",
            "appearanceMode"
        ] {
            defaults.removeObject(forKey: key)
        }
        AppSettings.shared.syncableClubs = []
    }

    /// Builds a syncable club for fixtures. The club id is the only thing
    /// `Settings.setClubEnabled` keys off of, so the other fields can be
    /// arbitrary.
    static func makeSyncableClub(id: Int, name: String = "Test Club", enabled: Bool = true) -> SyncableClub {
        SyncableClub(
            club: Club(
                id: id,
                name: name,
                memberCount: 10,
                city: "Test City",
                sportType: "cycling",
                profileMedium: nil
            ),
            isEnabled: enabled
        )
    }

    /// Builds a calendar event fixture for view tests.
    static func makeCalendarEvent(
        id: String = UUID().uuidString,
        title: String = "Morning Ride",
        offsetSeconds: TimeInterval = 3600,
        url: URL? = URL(string: "https://strava.com/clubs/1/group_events/1")
    ) -> CalendarEventData {
        CalendarEventData(
            id: id,
            title: title,
            startDate: Date().addingTimeInterval(offsetSeconds),
            url: url
        )
    }
}

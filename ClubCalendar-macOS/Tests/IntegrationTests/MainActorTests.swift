import Testing
import Foundation
@testable import ClubCalendarMac
@testable import ClubCalendarCore

@Suite("MainActor Tests")
@MainActor
struct MainActorTests {
    // MARK: - AppSettings Tests

    @Test("AppSettings syncInterval getter returns correct value")
    func appSettingsSyncIntervalGetter() {
        // Access the shared instance's syncInterval
        let settings = AppSettings.shared
        let originalMinutes = settings.syncIntervalMinutes

        // Set to known value
        settings.syncIntervalMinutes = 60
        #expect(settings.syncInterval == .oneHour)

        settings.syncIntervalMinutes = 15
        #expect(settings.syncInterval == .fifteenMinutes)

        settings.syncIntervalMinutes = 30
        #expect(settings.syncInterval == .thirtyMinutes)

        settings.syncIntervalMinutes = 120
        #expect(settings.syncInterval == .twoHours)

        settings.syncIntervalMinutes = 0
        #expect(settings.syncInterval == .never)

        // Unknown value defaults to oneHour
        settings.syncIntervalMinutes = 999
        #expect(settings.syncInterval == .oneHour)

        // Restore original
        settings.syncIntervalMinutes = originalMinutes
    }

    @Test("AppSettings syncInterval setter updates minutes")
    func appSettingsSyncIntervalSetter() {
        let settings = AppSettings.shared
        let originalMinutes = settings.syncIntervalMinutes

        settings.syncInterval = .fifteenMinutes
        #expect(settings.syncIntervalMinutes == 15)

        settings.syncInterval = .thirtyMinutes
        #expect(settings.syncIntervalMinutes == 30)

        settings.syncInterval = .oneHour
        #expect(settings.syncIntervalMinutes == 60)

        settings.syncInterval = .twoHours
        #expect(settings.syncIntervalMinutes == 120)

        settings.syncInterval = .never
        #expect(settings.syncIntervalMinutes == 0)

        // Restore original
        settings.syncIntervalMinutes = originalMinutes
    }

    @Test("AppSettings syncableClubs empty data returns empty array")
    func appSettingsSyncableClubsEmpty() {
        let settings = AppSettings.shared
        let originalData = settings.syncableClubs

        // Clear clubs
        settings.syncableClubs = []
        #expect(settings.syncableClubs.isEmpty)
        #expect(settings.enabledClubIds.isEmpty)

        // Restore
        settings.syncableClubs = originalData
    }

    @Test("AppSettings enabledClubIds filters correctly")
    func appSettingsEnabledClubIds() {
        let settings = AppSettings.shared
        let originalData = settings.syncableClubs

        let clubs = [
            SyncableClub(
                club: Club(id: 1, name: "Club 1", memberCount: 10, city: nil, sportType: nil, profileMedium: nil),
                isEnabled: true
            ),
            SyncableClub(
                club: Club(id: 2, name: "Club 2", memberCount: 20, city: nil, sportType: nil, profileMedium: nil),
                isEnabled: false
            ),
            SyncableClub(
                club: Club(id: 3, name: "Club 3", memberCount: 30, city: nil, sportType: nil, profileMedium: nil),
                isEnabled: true
            )
        ]

        settings.syncableClubs = clubs
        #expect(settings.enabledClubIds.count == 2)
        #expect(settings.enabledClubIds.contains(1))
        #expect(!settings.enabledClubIds.contains(2))
        #expect(settings.enabledClubIds.contains(3))

        // Restore
        settings.syncableClubs = originalData
    }

    @Test("AppSettings updateClubs preserves enabled state")
    func appSettingsUpdateClubsPreservesState() {
        let settings = AppSettings.shared
        let originalData = settings.syncableClubs

        // Initial clubs
        let initialClubs = [
            Club(id: 1, name: "Club 1", memberCount: 10, city: nil, sportType: nil, profileMedium: nil),
            Club(id: 2, name: "Club 2", memberCount: 20, city: nil, sportType: nil, profileMedium: nil)
        ]
        settings.updateClubs(initialClubs)

        // Verify both are enabled by default
        #expect(settings.enabledClubIds.count == 2)

        // Disable club 1
        settings.setClubEnabled(1, enabled: false)
        #expect(!settings.enabledClubIds.contains(1))
        #expect(settings.enabledClubIds.contains(2))

        // Update with new clubs (including club 1)
        let updatedClubs = [
            Club(id: 1, name: "Club 1 Updated", memberCount: 15, city: nil, sportType: nil, profileMedium: nil),
            Club(id: 2, name: "Club 2 Updated", memberCount: 25, city: nil, sportType: nil, profileMedium: nil),
            Club(id: 3, name: "New Club 3", memberCount: 35, city: nil, sportType: nil, profileMedium: nil)
        ]
        settings.updateClubs(updatedClubs)

        // Club 1 should still be disabled, club 2 enabled, club 3 enabled (new)
        #expect(!settings.enabledClubIds.contains(1))
        #expect(settings.enabledClubIds.contains(2))
        #expect(settings.enabledClubIds.contains(3))

        // Restore
        settings.syncableClubs = originalData
    }

    @Test("AppSettings setClubEnabled toggles club state")
    func appSettingsSetClubEnabled() {
        let settings = AppSettings.shared
        let originalData = settings.syncableClubs

        let clubs = [
            SyncableClub(
                club: Club(id: 1, name: "Test Club", memberCount: 10, city: nil, sportType: nil, profileMedium: nil),
                isEnabled: true
            )
        ]
        settings.syncableClubs = clubs

        #expect(settings.enabledClubIds.contains(1))

        settings.setClubEnabled(1, enabled: false)
        #expect(!settings.enabledClubIds.contains(1))

        settings.setClubEnabled(1, enabled: true)
        #expect(settings.enabledClubIds.contains(1))

        // Setting non-existent club does nothing
        settings.setClubEnabled(999, enabled: true)
        #expect(settings.syncableClubs.count == 1)

        // Restore
        settings.syncableClubs = originalData
    }

    // MARK: - SyncService Tests

    @Test("SyncService lastSyncTimeFormatted returns nil when no sync")
    func syncServiceLastSyncTimeFormattedNil() {
        let stravaService = StravaService()
        let calendarService = CalendarService()
        let syncService = SyncService(stravaService: stravaService, calendarService: calendarService)

        #expect(syncService.lastSyncTimeFormatted == nil)
    }

    @Test("SyncService syncInProgress is initially false")
    func syncServiceSyncInProgressInitiallyFalse() {
        let stravaService = StravaService()
        let calendarService = CalendarService()
        let syncService = SyncService(stravaService: stravaService, calendarService: calendarService)

        #expect(syncService.syncInProgress == false)
    }

    @Test("SyncService stopAutoSync handles nil timer")
    func syncServiceStopAutoSyncHandlesNilTimer() {
        let stravaService = StravaService()
        let calendarService = CalendarService()
        let syncService = SyncService(stravaService: stravaService, calendarService: calendarService)

        // Should not crash when timer is nil
        syncService.stopAutoSync()
        #expect(syncService.syncInProgress == false)
    }

    @Test("SyncService restartAutoSync calls startAutoSync")
    func syncServiceRestartAutoSync() {
        let stravaService = StravaService()
        let calendarService = CalendarService()
        let settings = AppSettings.shared

        let originalInterval = settings.syncInterval
        settings.syncInterval = .never  // Prevent actual timer creation

        let syncService = SyncService(stravaService: stravaService, calendarService: calendarService, settings: settings)

        syncService.restartAutoSync()
        // With .never interval, no timer should be created
        #expect(syncService.syncInProgress == false)

        settings.syncInterval = originalInterval
    }
}

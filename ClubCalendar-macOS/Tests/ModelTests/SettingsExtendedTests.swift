import Testing
import Foundation
@testable import ClubCalendarMac
@testable import ClubCalendarCore

@Suite("Settings Extended Tests")
struct SettingsExtendedTests {
    // MARK: - SyncInterval Tests

    @Test("SyncInterval rawValue matches minutes")
    func syncIntervalRawValueMatchesMinutes() {
        #expect(SyncInterval.fifteenMinutes.rawValue == 15)
        #expect(SyncInterval.thirtyMinutes.rawValue == 30)
        #expect(SyncInterval.oneHour.rawValue == 60)
        #expect(SyncInterval.twoHours.rawValue == 120)
        #expect(SyncInterval.never.rawValue == 0)
    }

    @Test("SyncInterval displayName is human readable")
    func syncIntervalDisplayNameIsHumanReadable() {
        #expect(SyncInterval.fifteenMinutes.displayName.contains("15"))
        #expect(SyncInterval.thirtyMinutes.displayName.contains("30"))
        #expect(SyncInterval.oneHour.displayName.contains("hour") || SyncInterval.oneHour.displayName.contains("1"))
        #expect(SyncInterval.twoHours.displayName.contains("2"))
        #expect(SyncInterval.never.displayName.lowercased().contains("never"))
    }

    @Test("SyncInterval allCases contains all values")
    func syncIntervalAllCasesContainsAll() {
        let allCases = SyncInterval.allCases
        #expect(allCases.count == 5)
        #expect(allCases.contains(.fifteenMinutes))
        #expect(allCases.contains(.thirtyMinutes))
        #expect(allCases.contains(.oneHour))
        #expect(allCases.contains(.twoHours))
        #expect(allCases.contains(.never))
    }

    @Test("SyncInterval Identifiable conformance")
    func syncIntervalIdentifiable() {
        let intervals = SyncInterval.allCases
        let ids = Set(intervals.map(\.id))
        #expect(ids.count == intervals.count)
    }

    // MARK: - SyncableClub Tests

    @Test("SyncableClub initialization")
    func syncableClubInitialization() {
        let club = Club(
            id: 1,
            name: "Test Club",
            memberCount: 100,
            city: "Amsterdam",
            sportType: "cycling",
            profileMedium: "http://example.com/image.jpg"
        )

        let syncable = SyncableClub(club: club, isEnabled: true)

        #expect(syncable.club.id == 1)
        #expect(syncable.club.name == "Test Club")
        #expect(syncable.isEnabled == true)
    }

    @Test("SyncableClub with isEnabled true")
    func syncableClubWithIsEnabledTrue() {
        let club = Club(
            id: 1,
            name: "Test",
            memberCount: 10,
            city: nil,
            sportType: nil,
            profileMedium: nil
        )

        let syncable = SyncableClub(club: club, isEnabled: true)

        #expect(syncable.isEnabled == true)
    }

    @Test("SyncableClub with isEnabled false")
    func syncableClubWithIsEnabledFalse() {
        let club = Club(
            id: 1,
            name: "Test",
            memberCount: 10,
            city: nil,
            sportType: nil,
            profileMedium: nil
        )

        let syncable = SyncableClub(club: club, isEnabled: false)

        #expect(syncable.isEnabled == false)
    }

    @Test("SyncableClub Identifiable uses club id")
    func syncableClubIdentifiable() {
        let club1 = Club(id: 100, name: "Club 1", memberCount: 10, city: nil, sportType: nil, profileMedium: nil)
        let club2 = Club(id: 200, name: "Club 2", memberCount: 20, city: nil, sportType: nil, profileMedium: nil)

        let syncable1 = SyncableClub(club: club1, isEnabled: true)
        let syncable2 = SyncableClub(club: club2, isEnabled: true)

        #expect(syncable1.id == 100)
        #expect(syncable2.id == 200)
    }

    @Test("SyncableClub encodes and decodes correctly")
    func syncableClubEncodesAndDecodes() throws {
        let club = Club(
            id: 42,
            name: "Encoded Club",
            memberCount: 50,
            city: "Berlin",
            sportType: "running",
            profileMedium: nil
        )
        let original = SyncableClub(club: club, isEnabled: false)

        let encoder = JSONEncoder()
        let decoder = JSONDecoder()

        let data = try encoder.encode(original)
        let decoded = try decoder.decode(SyncableClub.self, from: data)

        #expect(decoded.club.id == original.club.id)
        #expect(decoded.club.name == original.club.name)
        #expect(decoded.isEnabled == original.isEnabled)
    }

    @Test("SyncableClub Sendable conformance")
    func syncableClubSendable() async {
        let club = Club(id: 1, name: "Test", memberCount: 10, city: nil, sportType: nil, profileMedium: nil)
        let syncable = SyncableClub(club: club, isEnabled: true)

        let task = Task { @Sendable in
            return syncable.isEnabled
        }

        let enabled = await task.value
        #expect(enabled == true)
    }

    // MARK: - AppSettings Tests

    @Test("AppSettings syncInterval getter and setter")
    @MainActor
    func appSettingsSyncIntervalGetterSetter() {
        let settings = AppSettings.shared
        let originalMinutes = settings.syncIntervalMinutes

        // Test setting and getting various intervals
        for interval in SyncInterval.allCases {
            settings.syncInterval = interval
            #expect(settings.syncInterval == interval)
            #expect(settings.syncIntervalMinutes == interval.rawValue)
        }

        // Restore original
        settings.syncIntervalMinutes = originalMinutes
    }

    @Test("AppSettings syncInterval getter with unknown value")
    @MainActor
    func appSettingsSyncIntervalGetterUnknown() {
        let settings = AppSettings.shared
        let originalMinutes = settings.syncIntervalMinutes

        settings.syncIntervalMinutes = 45  // Not a valid interval
        #expect(settings.syncInterval == .oneHour)  // Should default to 1 hour

        settings.syncIntervalMinutes = -1
        #expect(settings.syncInterval == .oneHour)  // Should default to 1 hour

        // Restore original
        settings.syncIntervalMinutes = originalMinutes
    }

    @Test("AppSettings enabledClubIds returns only enabled clubs")
    @MainActor
    func appSettingsEnabledClubIds() {
        let settings = AppSettings.shared
        let originalClubs = settings.syncableClubs

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

        let enabledIds = settings.enabledClubIds
        #expect(enabledIds.count == 2)
        #expect(enabledIds.contains(1))
        #expect(!enabledIds.contains(2))
        #expect(enabledIds.contains(3))

        // Restore original
        settings.syncableClubs = originalClubs
    }

    @Test("AppSettings enabledClubIds with empty clubs")
    @MainActor
    func appSettingsEnabledClubIdsEmpty() {
        let settings = AppSettings.shared
        let originalClubs = settings.syncableClubs

        settings.syncableClubs = []

        #expect(settings.enabledClubIds.isEmpty)

        // Restore original
        settings.syncableClubs = originalClubs
    }

    @Test("AppSettings enabledClubIds with all disabled")
    @MainActor
    func appSettingsEnabledClubIdsAllDisabled() {
        let settings = AppSettings.shared
        let originalClubs = settings.syncableClubs

        let clubs = [
            SyncableClub(
                club: Club(id: 1, name: "Club 1", memberCount: 10, city: nil, sportType: nil, profileMedium: nil),
                isEnabled: false
            ),
            SyncableClub(
                club: Club(id: 2, name: "Club 2", memberCount: 20, city: nil, sportType: nil, profileMedium: nil),
                isEnabled: false
            )
        ]

        settings.syncableClubs = clubs

        #expect(settings.enabledClubIds.isEmpty)

        // Restore original
        settings.syncableClubs = originalClubs
    }

    @Test("AppSettings updateClubs adds new clubs as enabled")
    @MainActor
    func appSettingsUpdateClubsAddsNewClubs() {
        let settings = AppSettings.shared
        let originalClubs = settings.syncableClubs

        settings.syncableClubs = []

        let newClubs = [
            Club(id: 1, name: "Club 1", memberCount: 10, city: nil, sportType: nil, profileMedium: nil),
            Club(id: 2, name: "Club 2", memberCount: 20, city: nil, sportType: nil, profileMedium: nil)
        ]

        settings.updateClubs(newClubs)

        #expect(settings.syncableClubs.count == 2)
        #expect(settings.enabledClubIds.contains(1))
        #expect(settings.enabledClubIds.contains(2))

        // Restore original
        settings.syncableClubs = originalClubs
    }

    @Test("AppSettings updateClubs preserves enabled state")
    @MainActor
    func appSettingsUpdateClubsPreservesState() {
        let settings = AppSettings.shared
        let originalClubs = settings.syncableClubs

        // Set initial state with one disabled
        let initialClubs = [
            SyncableClub(
                club: Club(id: 1, name: "Club 1", memberCount: 10, city: nil, sportType: nil, profileMedium: nil),
                isEnabled: false
            ),
            SyncableClub(
                club: Club(id: 2, name: "Club 2", memberCount: 20, city: nil, sportType: nil, profileMedium: nil),
                isEnabled: true
            )
        ]
        settings.syncableClubs = initialClubs

        // Update with same clubs but updated info
        let updatedClubs = [
            Club(id: 1, name: "Club 1 Updated", memberCount: 15, city: nil, sportType: nil, profileMedium: nil),
            Club(id: 2, name: "Club 2 Updated", memberCount: 25, city: nil, sportType: nil, profileMedium: nil)
        ]

        settings.updateClubs(updatedClubs)

        // Enabled state should be preserved
        #expect(!settings.enabledClubIds.contains(1))  // Was disabled, should stay disabled
        #expect(settings.enabledClubIds.contains(2))   // Was enabled, should stay enabled

        // But names should be updated
        let club1 = settings.syncableClubs.first { $0.id == 1 }
        #expect(club1?.club.name == "Club 1 Updated")

        // Restore original
        settings.syncableClubs = originalClubs
    }

    @Test("AppSettings updateClubs handles club removal")
    @MainActor
    func appSettingsUpdateClubsHandlesRemoval() {
        let settings = AppSettings.shared
        let originalClubs = settings.syncableClubs

        // Set initial state with 3 clubs
        let initialClubs = [
            SyncableClub(club: Club(id: 1, name: "Club 1", memberCount: 10, city: nil, sportType: nil, profileMedium: nil), isEnabled: true),
            SyncableClub(club: Club(id: 2, name: "Club 2", memberCount: 20, city: nil, sportType: nil, profileMedium: nil), isEnabled: true),
            SyncableClub(club: Club(id: 3, name: "Club 3", memberCount: 30, city: nil, sportType: nil, profileMedium: nil), isEnabled: true)
        ]
        settings.syncableClubs = initialClubs

        // Update with only 2 clubs (one removed)
        let updatedClubs = [
            Club(id: 1, name: "Club 1", memberCount: 10, city: nil, sportType: nil, profileMedium: nil),
            Club(id: 3, name: "Club 3", memberCount: 30, city: nil, sportType: nil, profileMedium: nil)
        ]

        settings.updateClubs(updatedClubs)

        #expect(settings.syncableClubs.count == 2)
        #expect(settings.syncableClubs.contains { $0.id == 1 })
        #expect(!settings.syncableClubs.contains { $0.id == 2 })
        #expect(settings.syncableClubs.contains { $0.id == 3 })

        // Restore original
        settings.syncableClubs = originalClubs
    }

    @Test("AppSettings setClubEnabled enables club")
    @MainActor
    func appSettingsSetClubEnabledEnables() {
        let settings = AppSettings.shared
        let originalClubs = settings.syncableClubs

        let clubs = [
            SyncableClub(
                club: Club(id: 1, name: "Club", memberCount: 10, city: nil, sportType: nil, profileMedium: nil),
                isEnabled: false
            )
        ]
        settings.syncableClubs = clubs

        settings.setClubEnabled(1, enabled: true)

        #expect(settings.enabledClubIds.contains(1))

        // Restore original
        settings.syncableClubs = originalClubs
    }

    @Test("AppSettings setClubEnabled disables club")
    @MainActor
    func appSettingsSetClubEnabledDisables() {
        let settings = AppSettings.shared
        let originalClubs = settings.syncableClubs

        let clubs = [
            SyncableClub(
                club: Club(id: 1, name: "Club", memberCount: 10, city: nil, sportType: nil, profileMedium: nil),
                isEnabled: true
            )
        ]
        settings.syncableClubs = clubs

        settings.setClubEnabled(1, enabled: false)

        #expect(!settings.enabledClubIds.contains(1))

        // Restore original
        settings.syncableClubs = originalClubs
    }

    @Test("AppSettings setClubEnabled handles non-existent club")
    @MainActor
    func appSettingsSetClubEnabledNonExistent() {
        let settings = AppSettings.shared
        let originalClubs = settings.syncableClubs

        let clubs = [
            SyncableClub(
                club: Club(id: 1, name: "Club", memberCount: 10, city: nil, sportType: nil, profileMedium: nil),
                isEnabled: true
            )
        ]
        settings.syncableClubs = clubs

        // Should not crash when setting non-existent club
        settings.setClubEnabled(999, enabled: true)

        // Original club should be unchanged
        #expect(settings.syncableClubs.count == 1)
        #expect(settings.enabledClubIds.contains(1))

        // Restore original
        settings.syncableClubs = originalClubs
    }

    @Test("AppSettings calendarName default value")
    @MainActor
    func appSettingsCalendarNameDefault() {
        let settings = AppSettings.shared
        #expect(!settings.calendarName.isEmpty)
    }

    @Test("AppSettings maxMenuEvents default value")
    @MainActor
    func appSettingsMaxMenuEventsDefault() {
        let settings = AppSettings.shared
        #expect(settings.maxMenuEvents > 0)
    }

    @Test("AppSettings onboardingCompleted can be toggled")
    @MainActor
    func appSettingsOnboardingCompleted() {
        let settings = AppSettings.shared
        let originalValue = settings.onboardingCompleted

        settings.onboardingCompleted = !originalValue
        #expect(settings.onboardingCompleted == !originalValue)

        // Restore original
        settings.onboardingCompleted = originalValue
    }

}

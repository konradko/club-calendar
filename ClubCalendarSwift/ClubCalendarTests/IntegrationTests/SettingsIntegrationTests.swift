import Testing
import Foundation
@testable import ClubCalendar

@Suite("Settings Integration")
struct SettingsIntegrationTests {

    // MARK: - Sync Interval Tests

    @Test("Sync interval raw values", arguments: [
        (SyncInterval.fifteenMinutes, 15),
        (SyncInterval.thirtyMinutes, 30),
        (SyncInterval.oneHour, 60),
        (SyncInterval.twoHours, 120),
        (SyncInterval.never, 0)
    ])
    func syncIntervalRawValues(interval: SyncInterval, expected: Int) {
        #expect(interval.rawValue == expected)
    }

    @Test("Sync interval display names", arguments: [
        (SyncInterval.fifteenMinutes, "Every 15 minutes"),
        (SyncInterval.thirtyMinutes, "Every 30 minutes"),
        (SyncInterval.oneHour, "Every hour"),
        (SyncInterval.twoHours, "Every 2 hours"),
        (SyncInterval.never, "Never")
    ])
    func syncIntervalDisplayNames(interval: SyncInterval, expected: String) {
        #expect(interval.displayName == expected)
    }

    @Test("All sync intervals are covered")
    func allSyncIntervalsAreCovered() {
        let allCases = SyncInterval.allCases
        #expect(allCases.count == 5)

        // Verify no duplicate IDs
        let ids = allCases.map(\.id)
        #expect(Set(ids).count == ids.count)
    }

    // MARK: - Syncable Club Tests

    @Test("SyncableClub toggling")
    func syncableClubToggling() {
        let club = Club(
            id: 1,
            name: "Test Club",
            memberCount: 100,
            city: "Amsterdam",
            sportType: "cycling",
            profileMedium: nil
        )

        var syncable = SyncableClub(club: club, isEnabled: true)

        // Initially enabled
        #expect(syncable.isEnabled == true)

        // Toggle off
        syncable.isEnabled = false
        #expect(syncable.isEnabled == false)

        // Toggle back on
        syncable.isEnabled = true
        #expect(syncable.isEnabled == true)
    }

    @Test("SyncableClub ID delegation")
    func syncableClubIdDelegation() {
        let club = Club(
            id: 42,
            name: "ID Test Club",
            memberCount: 50,
            city: nil,
            sportType: nil,
            profileMedium: nil
        )

        let syncable = SyncableClub(club: club, isEnabled: true)

        // ID should delegate to underlying club
        #expect(syncable.id == 42)
        #expect(syncable.id == syncable.club.id)
    }

    @Test("SyncableClub encodes and decodes")
    func syncableClubEncodesAndDecodes() throws {
        let club = Club(
            id: 123,
            name: "Serialization Club",
            memberCount: 75,
            city: "Berlin",
            sportType: "running",
            profileMedium: "https://example.com/image.jpg"
        )

        let syncable = SyncableClub(club: club, isEnabled: false)

        let encoder = JSONEncoder()
        let decoder = JSONDecoder()

        let encoded = try encoder.encode(syncable)
        let decoded = try decoder.decode(SyncableClub.self, from: encoded)

        #expect(decoded.id == syncable.id)
        #expect(decoded.isEnabled == syncable.isEnabled)
        #expect(decoded.club.name == syncable.club.name)
    }

    @Test("Multiple SyncableClubs serialization")
    func multipleSyncableClubsSerialization() throws {
        let clubs = [
            Club(id: 1, name: "Club A", memberCount: 10, city: nil, sportType: nil, profileMedium: nil),
            Club(id: 2, name: "Club B", memberCount: 20, city: nil, sportType: nil, profileMedium: nil),
            Club(id: 3, name: "Club C", memberCount: 30, city: nil, sportType: nil, profileMedium: nil)
        ]

        let syncableClubs = [
            SyncableClub(club: clubs[0], isEnabled: true),
            SyncableClub(club: clubs[1], isEnabled: false),
            SyncableClub(club: clubs[2], isEnabled: true)
        ]

        let encoder = JSONEncoder()
        let decoder = JSONDecoder()

        let encoded = try encoder.encode(syncableClubs)
        let decoded = try decoder.decode([SyncableClub].self, from: encoded)

        #expect(decoded.count == 3)
        #expect(decoded[0].isEnabled == true)
        #expect(decoded[1].isEnabled == false)
        #expect(decoded[2].isEnabled == true)
    }

    // MARK: - Auth Error Tests

    @Test("Auth error descriptions are meaningful")
    func authErrorDescriptions() {
        let errors: [AuthError] = [
            .noCredentials,
            .cancelled,
            .noCallbackURL,
            .noAuthCode,
            .stravaError("access_denied"),
            .failedToStart
        ]

        for error in errors {
            #expect(error.errorDescription != nil)
            #expect(!error.errorDescription!.isEmpty)
        }
    }

    // MARK: - Calendar Error Tests

    @Test("Calendar error descriptions are meaningful")
    func calendarErrorDescriptions() {
        let errors: [CalendarError] = [
            .accessDenied,
            .accessRestricted,
            .calendarNotFound,
            .eventCreationFailed,
            .eventUpdateFailed,
            .unknownError(NSError(domain: "test", code: 1))
        ]

        for error in errors {
            #expect(error.errorDescription != nil)
            #expect(!error.errorDescription!.isEmpty)
        }
    }

    // MARK: - Calendar Access Status Tests

    @Test("Calendar access status values")
    func calendarAccessStatusValues() {
        let statuses: [CalendarAccessStatus] = [.authorized, .denied, .restricted, .notDetermined]
        #expect(statuses.count == 4)
    }
}

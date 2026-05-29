import Testing
import Foundation
@testable import ClubCalendarMac
@testable import ClubCalendarCore

@Suite("Settings Model")
struct SettingsTests {
    // MARK: - SyncInterval Tests

    @Test("SyncInterval raw values")
    func syncIntervalRawValues() {
        #expect(SyncInterval.fifteenMinutes.rawValue == 15)
        #expect(SyncInterval.thirtyMinutes.rawValue == 30)
        #expect(SyncInterval.oneHour.rawValue == 60)
        #expect(SyncInterval.twoHours.rawValue == 120)
        #expect(SyncInterval.never.rawValue == 0)
    }

    @Test("SyncInterval display names")
    func syncIntervalDisplayNames() {
        #expect(SyncInterval.fifteenMinutes.displayName == "Every 15 minutes")
        #expect(SyncInterval.thirtyMinutes.displayName == "Every 30 minutes")
        #expect(SyncInterval.oneHour.displayName == "Every hour")
        #expect(SyncInterval.twoHours.displayName == "Every 2 hours")
        #expect(SyncInterval.never.displayName == "Never")
    }

    @Test("SyncInterval id matches rawValue")
    func syncIntervalIdMatchesRawValue() {
        for interval in SyncInterval.allCases {
            #expect(interval.id == interval.rawValue)
        }
    }

    @Test("SyncInterval allCases count")
    func syncIntervalAllCasesCount() {
        #expect(SyncInterval.allCases.count == 5)
    }

    @Test("SyncInterval Identifiable conformance")
    func syncIntervalIdentifiable() {
        let intervals = SyncInterval.allCases
        let ids = Set(intervals.map(\.id))
        #expect(ids.count == intervals.count)
    }

    @Test("SyncInterval init from rawValue")
    func syncIntervalInitFromRawValue() {
        #expect(SyncInterval(rawValue: 15) == .fifteenMinutes)
        #expect(SyncInterval(rawValue: 30) == .thirtyMinutes)
        #expect(SyncInterval(rawValue: 60) == .oneHour)
        #expect(SyncInterval(rawValue: 120) == .twoHours)
        #expect(SyncInterval(rawValue: 0) == .never)
        #expect(SyncInterval(rawValue: 999) == nil)
    }

    // MARK: - SyncableClub Tests

    @Test("SyncableClub encodes and decodes")
    func syncableClubEncodesAndDecodes() throws {
        let club = Club(
            id: 123,
            name: "Test Club",
            memberCount: 50,
            city: "Amsterdam",
            sportType: "cycling",
            profileMedium: "https://example.com/image.jpg"
        )
        let syncable = SyncableClub(club: club, isEnabled: true)

        let encoder = JSONEncoder()
        let decoder = JSONDecoder()

        let encoded = try encoder.encode(syncable)
        let decoded = try decoder.decode(SyncableClub.self, from: encoded)

        #expect(decoded.id == syncable.id)
        #expect(decoded.club.name == syncable.club.name)
        #expect(decoded.isEnabled == syncable.isEnabled)
    }

    @Test("SyncableClub id delegates to club")
    func syncableClubIdDelegatesToClub() {
        let club = Club(id: 42, name: "Test", memberCount: 1, city: nil, sportType: nil, profileMedium: nil)
        let syncable = SyncableClub(club: club, isEnabled: true)
        #expect(syncable.id == 42)
        #expect(syncable.id == club.id)
    }

    @Test("SyncableClub Hashable conformance")
    func syncableClubHashable() {
        let club1 = Club(id: 1, name: "Club A", memberCount: 10, city: nil, sportType: nil, profileMedium: nil)
        let club2 = Club(id: 2, name: "Club B", memberCount: 20, city: nil, sportType: nil, profileMedium: nil)

        let syncable1 = SyncableClub(club: club1, isEnabled: true)
        let syncable2 = SyncableClub(club: club2, isEnabled: false)

        var set = Set<SyncableClub>()
        set.insert(syncable1)
        set.insert(syncable2)
        #expect(set.count == 2)
    }

    @Test("SyncableClub isEnabled can be toggled")
    func syncableClubIsEnabledCanBeToggled() {
        let club = Club(id: 1, name: "Test", memberCount: 1, city: nil, sportType: nil, profileMedium: nil)
        var syncable = SyncableClub(club: club, isEnabled: false)

        #expect(syncable.isEnabled == false)
        syncable.isEnabled = true
        #expect(syncable.isEnabled == true)
        syncable.isEnabled = false
        #expect(syncable.isEnabled == false)
    }

    // MARK: - Club Array Filtering Tests

    @Test("Filter enabled clubs from syncable clubs array")
    func filterEnabledClubs() {
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

        let enabledIds = Set(syncableClubs.filter(\.isEnabled).map(\.id))
        #expect(enabledIds.count == 2)
        #expect(enabledIds.contains(1))
        #expect(!enabledIds.contains(2))
        #expect(enabledIds.contains(3))
    }

    @Test("Empty syncable clubs array produces empty enabled ids")
    func emptySyncableClubsProducesEmptyEnabledIds() {
        let syncableClubs: [SyncableClub] = []
        let enabledIds = Set(syncableClubs.filter(\.isEnabled).map(\.id))
        #expect(enabledIds.isEmpty)
    }

    @Test("All clubs disabled produces empty enabled ids")
    func allClubsDisabledProducesEmptyEnabledIds() {
        let clubs = [
            Club(id: 1, name: "Club A", memberCount: 10, city: nil, sportType: nil, profileMedium: nil),
            Club(id: 2, name: "Club B", memberCount: 20, city: nil, sportType: nil, profileMedium: nil)
        ]

        let syncableClubs = [
            SyncableClub(club: clubs[0], isEnabled: false),
            SyncableClub(club: clubs[1], isEnabled: false)
        ]

        let enabledIds = Set(syncableClubs.filter(\.isEnabled).map(\.id))
        #expect(enabledIds.isEmpty)
    }

    @Test("All clubs enabled produces all ids")
    func allClubsEnabledProducesAllIds() {
        let clubs = [
            Club(id: 1, name: "Club A", memberCount: 10, city: nil, sportType: nil, profileMedium: nil),
            Club(id: 2, name: "Club B", memberCount: 20, city: nil, sportType: nil, profileMedium: nil)
        ]

        let syncableClubs = [
            SyncableClub(club: clubs[0], isEnabled: true),
            SyncableClub(club: clubs[1], isEnabled: true)
        ]

        let enabledIds = Set(syncableClubs.filter(\.isEnabled).map(\.id))
        #expect(enabledIds.count == 2)
        #expect(enabledIds.contains(1))
        #expect(enabledIds.contains(2))
    }

    // MARK: - SyncInterval Conversion Tests

    @Test("SyncInterval can be created from all valid raw values")
    func syncIntervalFromValidRawValues() {
        let validValues: [(Int, SyncInterval)] = [
            (0, .never),
            (15, .fifteenMinutes),
            (30, .thirtyMinutes),
            (60, .oneHour),
            (120, .twoHours)
        ]

        for (rawValue, expected) in validValues {
            let interval = SyncInterval(rawValue: rawValue)
            #expect(interval == expected)
        }
    }

    @Test("SyncInterval returns nil for invalid raw values")
    func syncIntervalFromInvalidRawValues() {
        let invalidValues = [1, 5, 10, 45, 90, 180, 240, -1, 1000]

        for value in invalidValues {
            let interval = SyncInterval(rawValue: value)
            #expect(interval == nil)
        }
    }

    // MARK: - Club Encoding/Decoding Round Trip Tests

    @Test("Club with all fields encodes and decodes correctly")
    func clubWithAllFieldsRoundTrip() throws {
        let original = Club(
            id: 999,
            name: "Full Featured Club",
            memberCount: 500,
            city: "New York",
            sportType: "triathlon",
            profileMedium: "https://example.com/profile.png"
        )

        let encoder = JSONEncoder()
        let decoder = JSONDecoder()

        let data = try encoder.encode(original)
        let decoded = try decoder.decode(Club.self, from: data)

        #expect(decoded.id == original.id)
        #expect(decoded.name == original.name)
        #expect(decoded.memberCount == original.memberCount)
        #expect(decoded.city == original.city)
        #expect(decoded.sportType == original.sportType)
        #expect(decoded.profileMedium == original.profileMedium)
    }

    @Test("Club with nil optional fields encodes and decodes correctly")
    func clubWithNilFieldsRoundTrip() throws {
        let original = Club(
            id: 1,
            name: "Minimal Club",
            memberCount: 1,
            city: nil,
            sportType: nil,
            profileMedium: nil
        )

        let encoder = JSONEncoder()
        let decoder = JSONDecoder()

        let data = try encoder.encode(original)
        let decoded = try decoder.decode(Club.self, from: data)

        #expect(decoded.id == original.id)
        #expect(decoded.name == original.name)
        #expect(decoded.memberCount == original.memberCount)
        #expect(decoded.city == nil)
        #expect(decoded.sportType == nil)
        #expect(decoded.profileMedium == nil)
    }

    // MARK: - SyncableClub Array Operations Tests

    @Test("Array of SyncableClubs encodes and decodes correctly")
    func syncableClubArrayRoundTrip() throws {
        let clubs = [
            SyncableClub(
                club: Club(id: 1, name: "Club 1", memberCount: 10, city: "A", sportType: "cycling", profileMedium: nil),
                isEnabled: true
            ),
            SyncableClub(
                club: Club(id: 2, name: "Club 2", memberCount: 20, city: "B", sportType: "running", profileMedium: nil),
                isEnabled: false
            ),
            SyncableClub(
                club: Club(id: 3, name: "Club 3", memberCount: 30, city: nil, sportType: nil, profileMedium: nil),
                isEnabled: true
            )
        ]

        let encoder = JSONEncoder()
        let decoder = JSONDecoder()

        let data = try encoder.encode(clubs)
        let decoded = try decoder.decode([SyncableClub].self, from: data)

        #expect(decoded.count == 3)
        #expect(decoded[0].id == 1)
        #expect(decoded[0].isEnabled == true)
        #expect(decoded[1].id == 2)
        #expect(decoded[1].isEnabled == false)
        #expect(decoded[2].id == 3)
        #expect(decoded[2].isEnabled == true)
    }

    @Test("Empty SyncableClub array encodes and decodes correctly")
    func emptySyncableClubArrayRoundTrip() throws {
        let clubs: [SyncableClub] = []

        let encoder = JSONEncoder()
        let decoder = JSONDecoder()

        let data = try encoder.encode(clubs)
        let decoded = try decoder.decode([SyncableClub].self, from: data)

        #expect(decoded.isEmpty)
    }
}

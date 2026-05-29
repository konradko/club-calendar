import Testing
import Foundation
@testable import ClubCalendarMac
@testable import ClubCalendarCore

@Suite("Club Extended Tests")
struct ClubExtendedTests {
    // MARK: - Club Tests

    @Test("Club with all fields")
    func clubWithAllFields() {
        let club = Club(
            id: 12345,
            name: "Amsterdam Cycling Club",
            memberCount: 500,
            city: "Amsterdam",
            sportType: "cycling",
            profileMedium: "https://example.com/profile.jpg"
        )

        #expect(club.id == 12345)
        #expect(club.name == "Amsterdam Cycling Club")
        #expect(club.memberCount == 500)
        #expect(club.city == "Amsterdam")
        #expect(club.sportType == "cycling")
        #expect(club.profileMedium == "https://example.com/profile.jpg")
    }

    @Test("Club with nil optional fields")
    func clubWithNilOptionalFields() {
        let club = Club(
            id: 1,
            name: "Test Club",
            memberCount: 10,
            city: nil,
            sportType: nil,
            profileMedium: nil
        )

        #expect(club.city == nil)
        #expect(club.sportType == nil)
        #expect(club.profileMedium == nil)
    }

    @Test("Club Identifiable conformance")
    func clubIdentifiable() {
        let club1 = Club(id: 1, name: "Club 1", memberCount: 10, city: nil, sportType: nil, profileMedium: nil)
        let club2 = Club(id: 2, name: "Club 2", memberCount: 20, city: nil, sportType: nil, profileMedium: nil)

        #expect(club1.id == 1)
        #expect(club2.id == 2)
        #expect(club1.id != club2.id)
    }

    @Test("Club Hashable conformance")
    func clubHashable() {
        let club1 = Club(id: 1, name: "Club", memberCount: 10, city: nil, sportType: nil, profileMedium: nil)
        let club2 = Club(id: 1, name: "Club", memberCount: 10, city: nil, sportType: nil, profileMedium: nil)
        let club3 = Club(id: 2, name: "Club", memberCount: 10, city: nil, sportType: nil, profileMedium: nil)

        #expect(club1 == club2)
        #expect(club1 != club3)

        var set = Set<Club>()
        set.insert(club1)
        set.insert(club2)
        #expect(set.count == 1)

        set.insert(club3)
        #expect(set.count == 2)
    }

    @Test("Club Sendable conformance")
    func clubSendable() async {
        let club = Club(id: 1, name: "Test", memberCount: 10, city: "City", sportType: "cycling", profileMedium: nil)

        let task = Task { @Sendable in
            return club.name
        }

        let name = await task.value
        #expect(name == "Test")
    }

    @Test("Club encodes and decodes correctly")
    func clubEncodesAndDecodes() throws {
        let original = Club(
            id: 42,
            name: "Test Club",
            memberCount: 100,
            city: "Berlin",
            sportType: "running",
            profileMedium: "https://example.com/img.jpg"
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

    @Test("Club decodes from Strava API JSON format")
    func clubDecodesFromStravaJSON() throws {
        let json = """
        {
            "id": 123456,
            "name": "Strava Club",
            "member_count": 250,
            "city": "San Francisco",
            "sport_type": "cycling",
            "profile_medium": "https://strava.com/clubs/123456/profile.jpg"
        }
        """

        let data = json.data(using: .utf8)!
        let club = try JSONDecoder().decode(Club.self, from: data)

        #expect(club.id == 123456)
        #expect(club.name == "Strava Club")
        #expect(club.memberCount == 250)
        #expect(club.city == "San Francisco")
        #expect(club.sportType == "cycling")
        #expect(club.profileMedium == "https://strava.com/clubs/123456/profile.jpg")
    }

    @Test("Club decodes with missing optional fields")
    func clubDecodesWithMissingOptionals() throws {
        let json = """
        {
            "id": 1,
            "name": "Minimal Club",
            "member_count": 5
        }
        """

        let data = json.data(using: .utf8)!
        let club = try JSONDecoder().decode(Club.self, from: data)

        #expect(club.id == 1)
        #expect(club.name == "Minimal Club")
        #expect(club.memberCount == 5)
        #expect(club.city == nil)
        #expect(club.sportType == nil)
        #expect(club.profileMedium == nil)
    }

    @Test("Club with large member count")
    func clubWithLargeMemberCount() {
        let club = Club(
            id: 1,
            name: "Large Club",
            memberCount: 1_000_000,
            city: nil,
            sportType: nil,
            profileMedium: nil
        )

        #expect(club.memberCount == 1_000_000)
    }

    @Test("Club with special characters in name")
    func clubWithSpecialCharactersInName() throws {
        let club = Club(
            id: 1,
            name: "Vélo Club d'Été 🚴",
            memberCount: 10,
            city: "Montréal",
            sportType: nil,
            profileMedium: nil
        )

        #expect(club.name == "Vélo Club d'Été 🚴")
        #expect(club.city == "Montréal")

        // Verify encoding preserves special characters
        let encoder = JSONEncoder()
        let decoder = JSONDecoder()

        let data = try encoder.encode(club)
        let decoded = try decoder.decode(Club.self, from: data)

        #expect(decoded.name == club.name)
        #expect(decoded.city == club.city)
    }

    // MARK: - SyncableClub Tests

    @Test("SyncableClub initialization")
    func syncableClubInitialization() {
        let club = Club(id: 1, name: "Test", memberCount: 10, city: nil, sportType: nil, profileMedium: nil)
        let syncable = SyncableClub(club: club, isEnabled: true)

        #expect(syncable.club.id == 1)
        #expect(syncable.isEnabled == true)
        #expect(syncable.id == 1)  // id delegates to club.id
    }

    @Test("SyncableClub isEnabled can be modified")
    func syncableClubIsEnabledModifiable() {
        let club = Club(id: 1, name: "Test", memberCount: 10, city: nil, sportType: nil, profileMedium: nil)
        var syncable = SyncableClub(club: club, isEnabled: true)

        #expect(syncable.isEnabled == true)

        syncable.isEnabled = false
        #expect(syncable.isEnabled == false)

        syncable.isEnabled = true
        #expect(syncable.isEnabled == true)
    }

    @Test("SyncableClub Hashable conformance")
    func syncableClubHashable() {
        let club1 = Club(id: 1, name: "Club", memberCount: 10, city: nil, sportType: nil, profileMedium: nil)
        let club2 = Club(id: 2, name: "Club", memberCount: 10, city: nil, sportType: nil, profileMedium: nil)

        let syncable1 = SyncableClub(club: club1, isEnabled: true)
        let syncable2 = SyncableClub(club: club1, isEnabled: true)
        let syncable3 = SyncableClub(club: club2, isEnabled: true)
        let syncable4 = SyncableClub(club: club1, isEnabled: false)

        #expect(syncable1 == syncable2)
        #expect(syncable1 != syncable3)
        #expect(syncable1 != syncable4)  // Different isEnabled

        var set = Set<SyncableClub>()
        set.insert(syncable1)
        set.insert(syncable2)
        #expect(set.count == 1)
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

    @Test("SyncableClub encodes and decodes")
    func syncableClubEncodesAndDecodes() throws {
        let club = Club(id: 42, name: "Test Club", memberCount: 100, city: "City", sportType: "cycling", profileMedium: nil)
        let original = SyncableClub(club: club, isEnabled: false)

        let encoder = JSONEncoder()
        let decoder = JSONDecoder()

        let data = try encoder.encode(original)
        let decoded = try decoder.decode(SyncableClub.self, from: data)

        #expect(decoded.id == original.id)
        #expect(decoded.club.name == original.club.name)
        #expect(decoded.isEnabled == original.isEnabled)
    }

    @Test("Array of SyncableClub encodes and decodes")
    func syncableClubArrayEncodesAndDecodes() throws {
        let clubs = [
            SyncableClub(club: Club(id: 1, name: "Club 1", memberCount: 10, city: nil, sportType: nil, profileMedium: nil), isEnabled: true),
            SyncableClub(club: Club(id: 2, name: "Club 2", memberCount: 20, city: nil, sportType: nil, profileMedium: nil), isEnabled: false),
            SyncableClub(club: Club(id: 3, name: "Club 3", memberCount: 30, city: nil, sportType: nil, profileMedium: nil), isEnabled: true)
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

    @Test("Filtering enabled clubs from array")
    func filteringEnabledClubs() {
        let clubs = [
            SyncableClub(club: Club(id: 1, name: "Club 1", memberCount: 10, city: nil, sportType: nil, profileMedium: nil), isEnabled: true),
            SyncableClub(club: Club(id: 2, name: "Club 2", memberCount: 20, city: nil, sportType: nil, profileMedium: nil), isEnabled: false),
            SyncableClub(club: Club(id: 3, name: "Club 3", memberCount: 30, city: nil, sportType: nil, profileMedium: nil), isEnabled: true),
            SyncableClub(club: Club(id: 4, name: "Club 4", memberCount: 40, city: nil, sportType: nil, profileMedium: nil), isEnabled: false)
        ]

        let enabledClubs = clubs.filter(\.isEnabled)
        let enabledIds = Set(enabledClubs.map(\.id))

        #expect(enabledClubs.count == 2)
        #expect(enabledIds.contains(1))
        #expect(!enabledIds.contains(2))
        #expect(enabledIds.contains(3))
        #expect(!enabledIds.contains(4))
    }
}

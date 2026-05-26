import Testing
import Foundation
@testable import ClubCalendar

@Suite("Club Model")
struct ClubTests {
    @Test("Club decodes from Strava JSON")
    func clubDecodesFromJSON() throws {
        let json = """
        {
            "id": 12345,
            "name": "BikeClub Amsterdam",
            "member_count": 124,
            "city": "Amsterdam",
            "sport_type": "cycling",
            "profile_medium": "https://example.com/image.jpg"
        }
        """

        let data = json.data(using: .utf8)!
        let club = try JSONDecoder().decode(Club.self, from: data)

        #expect(club.id == 12345)
        #expect(club.name == "BikeClub Amsterdam")
        #expect(club.memberCount == 124)
        #expect(club.city == "Amsterdam")
        #expect(club.sportType == "cycling")
        #expect(club.profileMedium == "https://example.com/image.jpg")
    }

    @Test("Club decodes with missing optional fields")
    func clubDecodesWithMissingFields() throws {
        let json = """
        {
            "id": 99,
            "name": "Minimal Club",
            "member_count": 10
        }
        """

        let data = json.data(using: .utf8)!
        let club = try JSONDecoder().decode(Club.self, from: data)

        #expect(club.id == 99)
        #expect(club.name == "Minimal Club")
        #expect(club.memberCount == 10)
        #expect(club.city == nil)
        #expect(club.sportType == nil)
    }

    @Test("SyncableClub preserves enabled state")
    func syncableClubPreservesState() {
        let club = Club(
            id: 1,
            name: "Test Club",
            memberCount: 50,
            city: nil,
            sportType: nil,
            profileMedium: nil
        )

        var syncable = SyncableClub(club: club, isEnabled: true)
        #expect(syncable.isEnabled == true)
        #expect(syncable.id == 1)

        syncable.isEnabled = false
        #expect(syncable.isEnabled == false)
    }

    @Test("Club is Hashable")
    func clubIsHashable() {
        let club1 = Club(id: 1, name: "Club A", memberCount: 10, city: nil, sportType: nil, profileMedium: nil)
        let club2 = Club(id: 1, name: "Club A", memberCount: 10, city: nil, sportType: nil, profileMedium: nil)
        let club3 = Club(id: 2, name: "Club B", memberCount: 20, city: nil, sportType: nil, profileMedium: nil)

        #expect(club1 == club2)
        #expect(club1 != club3)

        var set = Set<Club>()
        set.insert(club1)
        set.insert(club2)
        #expect(set.count == 1)
    }

    @Test("Club encodes and decodes round-trip")
    func clubEncodesAndDecodes() throws {
        let club = Club(
            id: 42,
            name: "Round Trip Club",
            memberCount: 100,
            city: "Berlin",
            sportType: "running",
            profileMedium: "https://example.com/profile.jpg"
        )

        let encoded = try JSONEncoder().encode(club)
        let decoded = try JSONDecoder().decode(Club.self, from: encoded)

        #expect(club == decoded)
    }
}

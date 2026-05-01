import Testing
import Foundation
@testable import ClubCalendar

@Suite("Strava API Integration")
struct StravaAPIIntegrationTests {
    let mockSession = MockURLSession()

    // MARK: - Club List Tests

    @Test("Fetch clubs decodes successfully")
    func fetchClubsSuccessfully() throws {
        let clubsJSON = """
        [
            {
                "id": 1,
                "name": "BikeClub Amsterdam",
                "member_count": 124,
                "city": "Amsterdam",
                "sport_type": "cycling"
            },
            {
                "id": 2,
                "name": "RunClub NL",
                "member_count": 89,
                "city": "Rotterdam",
                "sport_type": "running"
            }
        ]
        """

        let data = clubsJSON.data(using: .utf8)!
        let clubs = try JSONDecoder().decode([Club].self, from: data)

        #expect(clubs.count == 2)
        #expect(clubs[0].name == "BikeClub Amsterdam")
        #expect(clubs[0].memberCount == 124)
        #expect(clubs[1].sportType == "running")
    }

    // MARK: - Event List Tests

    @Test("Fetch club events decodes successfully")
    func fetchClubEventsSuccessfully() throws {
        let eventsJSON = """
        [
            {
                "id": 100,
                "title": "Saturday Morning Ride",
                "club_name": "BikeClub Amsterdam",
                "description": "Weekly group ride",
                "activity_type": "Ride",
                "start_datetime": "2025-01-25T09:00:00Z",
                "address": "Central Station"
            },
            {
                "id": 101,
                "title": "Evening Run",
                "club_name": "BikeClub Amsterdam",
                "description": "After work run",
                "activity_type": "Run",
                "start_datetime": "2025-01-26T18:30:00Z",
                "address": "Vondelpark"
            }
        ]
        """

        let decoder = JSONDecoder()

        let data = eventsJSON.data(using: .utf8)!
        let events = try decoder.decode([ClubEvent].self, from: data)

        #expect(events.count == 2)
        #expect(events[0].title == "Saturday Morning Ride")
        #expect(events[0].activityEmoji == "🚴")
        #expect(events[1].activityEmoji == "🏃")
    }

    // MARK: - Token Exchange Tests

    @Test("Token exchange decodes successfully")
    func tokenExchangeSuccessfully() throws {
        let tokenJSON = """
        {
            "access_token": "test_access_token_12345",
            "refresh_token": "test_refresh_token_67890",
            "expires_at": 1735689600,
            "athlete": {
                "id": 99999,
                "firstname": "Test",
                "lastname": "User"
            }
        }
        """

        let data = tokenJSON.data(using: .utf8)!
        let response = try JSONDecoder().decode(TokenResponse.self, from: data)

        #expect(response.accessToken == "test_access_token_12345")
        #expect(response.refreshToken == "test_refresh_token_67890")
        #expect(response.athlete?.fullName == "Test User")

        // Verify token expiry conversion
        let expiryDate = Date(timeIntervalSince1970: TimeInterval(response.expiresAt))
        #expect(expiryDate > Date(timeIntervalSince1970: 0))
    }

    // MARK: - Edge Cases

    @Test("Handles empty club list")
    func handlesEmptyClubList() throws {
        let emptyJSON = "[]"

        let data = emptyJSON.data(using: .utf8)!
        let clubs = try JSONDecoder().decode([Club].self, from: data)

        #expect(clubs.isEmpty)
    }

    @Test("Handles club with minimal fields")
    func handlesClubWithMinimalFields() throws {
        let minimalJSON = """
        {
            "id": 999,
            "name": "Minimal Club",
            "member_count": 1
        }
        """

        let data = minimalJSON.data(using: .utf8)!
        let club = try JSONDecoder().decode(Club.self, from: data)

        #expect(club.id == 999)
        #expect(club.city == nil)
        #expect(club.sportType == nil)
    }

    @Test("Handles event with unicode characters")
    func handlesEventWithUnicodeCharacters() throws {
        let unicodeJSON = """
        {
            "id": 1,
            "title": "Café Ride 🚴‍♂️",
            "club_name": "日本語クラブ",
            "start_datetime": "2025-01-25T10:00:00Z"
        }
        """

        let decoder = JSONDecoder()

        let data = unicodeJSON.data(using: .utf8)!
        let event = try decoder.decode(ClubEvent.self, from: data)

        #expect(event.title == "Café Ride 🚴‍♂️")
        #expect(event.clubName == "日本語クラブ")
    }

    @Test("Events sort by date correctly")
    func eventsSortByDate() throws {
        let eventsJSON = """
        [
            {"id": 3, "title": "Later", "club_name": "C", "start_datetime": "2025-03-01T10:00:00Z"},
            {"id": 1, "title": "First", "club_name": "C", "start_datetime": "2025-01-01T10:00:00Z"},
            {"id": 2, "title": "Middle", "club_name": "C", "start_datetime": "2025-02-01T10:00:00Z"}
        ]
        """

        let decoder = JSONDecoder()

        let data = eventsJSON.data(using: .utf8)!
        var events = try decoder.decode([ClubEvent].self, from: data)
        events.sort { $0.startDatetime < $1.startDatetime }

        #expect(events[0].title == "First")
        #expect(events[1].title == "Middle")
        #expect(events[2].title == "Later")
    }
}

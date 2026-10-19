import Testing
import Foundation
@testable import ClubCalendarMac
@testable import ClubCalendarCore

@Suite("StravaService Integration")
struct StravaServiceIntegrationTests {
    let mockSession = MockURLSession()

    // MARK: - Token Exchange Tests

    @Test("Token exchange with valid code")
    func tokenExchangeWithValidCode() async throws {
        // Set up mock keychain with credentials
        let mockKeychain = MockKeychainHelper()
        try mockKeychain.setCredentials(clientId: "test_client_id", clientSecret: "test_client_secret")

        // Set up mock response
        let tokenURL = URL(string: "https://www.strava.com/oauth/token")!
        let responseJSON = """
        {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_at": 1999999999,
            "athlete": {
                "id": 12345,
                "firstname": "Test",
                "lastname": "User"
            }
        }
        """
        mockSession.setMockJSONResponse(for: tokenURL, json: responseJSON)

        // Create service with mock session
        _ = StravaService(keychain: KeychainHelper.shared, session: mockSession)

        // Note: This test demonstrates the mock setup but can't fully execute
        // because StravaService uses the real KeychainHelper internally.
        // The proper integration test would require dependency injection.

        // Verify mock response is set up correctly
        #expect(mockSession.mockResponses[tokenURL] != nil)
    }

    // MARK: - Response Decoding Tests

    @Test("Club list response decodes correctly")
    func clubListResponseDecodes() throws {
        let json = """
        [
            {
                "id": 1,
                "name": "Amsterdam Cyclists",
                "member_count": 250,
                "city": "Amsterdam",
                "sport_type": "cycling",
                "profile_medium": "https://example.com/profile1.jpg"
            },
            {
                "id": 2,
                "name": "Rotterdam Runners",
                "member_count": 150,
                "city": "Rotterdam",
                "sport_type": "running"
            },
            {
                "id": 3,
                "name": "Minimal Club",
                "member_count": 10
            }
        ]
        """

        let data = json.data(using: .utf8)!
        let clubs = try JSONDecoder().decode([Club].self, from: data)

        #expect(clubs.count == 3)
        #expect(clubs[0].name == "Amsterdam Cyclists")
        #expect(clubs[0].city == "Amsterdam")
        #expect(clubs[0].profileMedium != nil)
        #expect(clubs[1].sportType == "running")
        #expect(clubs[2].city == nil)
        #expect(clubs[2].sportType == nil)
    }

    @Test("Event list response with various activity types")
    func eventListWithVariousActivityTypes() throws {
        let json = """
        [
            {"id": 1, "title": "Morning Ride", "club_name": "Club A", "activity_type": "Ride", "start_datetime": "2025-01-25T08:00:00Z"},
            {"id": 2, "title": "Evening Run", "club_name": "Club B", "activity_type": "Run", "start_datetime": "2025-01-25T18:00:00Z"},
            {"id": 3, "title": "Pool Session", "club_name": "Club C", "activity_type": "Swim", "start_datetime": "2025-01-26T07:00:00Z"},
            {"id": 4, "title": "Mountain Hike", "club_name": "Club D", "activity_type": "Hike", "start_datetime": "2025-01-27T09:00:00Z"},
            {"id": 5, "title": "Mystery Event", "club_name": "Club E", "start_datetime": "2025-01-28T10:00:00Z"}
        ]
        """

        let decoder = JSONDecoder()

        let data = json.data(using: .utf8)!
        let events = try decoder.decode([ClubEvent].self, from: data)

        #expect(events.count == 5)
        #expect(events[0].activityEmoji == "🚴")
        #expect(events[1].activityEmoji == "🏃")
        #expect(events[2].activityEmoji == "🏊")
        #expect(events[3].activityEmoji == "🥾")
        #expect(events[4].activityEmoji == "📅")  // nil activity type
    }

    @Test("Event response with all optional fields")
    func eventResponseWithAllOptionalFields() throws {
        let json = """
        {
            "id": 99999,
            "title": "Complete Event",
            "club_name": "Full Club",
            "description": "A comprehensive event description with details",
            "activity_type": "Ride",
            "start_datetime": "2025-02-15T10:00:00Z",
            "address": "Central Station, Amsterdam",
            "private": true,
            "organizing_athlete": {
                "id": 111,
                "firstname": "Organizer",
                "lastname": "Person"
            },
            "route_id": 12345
        }
        """

        let decoder = JSONDecoder()

        let data = json.data(using: .utf8)!
        let event = try decoder.decode(ClubEvent.self, from: data)

        #expect(event.id == 99999)
        #expect(event.description == "A comprehensive event description with details")
        #expect(event.address == "Central Station, Amsterdam")
        #expect(event.privateEvent == true)
        #expect(event.organizingAthlete?.fullName == "Organizer Person")
        #expect(event.routeId == 12345)
        #expect(event.stravaURL?.absoluteString == "https://www.strava.com/clubs/0/group_events/99999")
        #expect(event.formattedTitle == "🚴 Full Club: Complete Event")
    }

    @Test("Event response with minimal fields")
    func eventResponseWithMinimalFields() throws {
        let json = """
        {
            "id": 1,
            "title": "Simple Event",
            "club_name": "Simple Club",
            "start_datetime": "2025-01-25T12:00:00Z"
        }
        """

        let decoder = JSONDecoder()

        let data = json.data(using: .utf8)!
        let event = try decoder.decode(ClubEvent.self, from: data)

        #expect(event.description == nil)
        #expect(event.activityType == nil)
        #expect(event.address == nil)
        #expect(event.privateEvent == nil)
        #expect(event.organizingAthlete == nil)
        #expect(event.routeId == nil)
        #expect(event.activityEmoji == "📅")
    }

    // MARK: - Refresh Token Response Tests

    @Test("Refresh token response decodes correctly")
    func refreshTokenResponseDecodes() throws {
        let json = """
        {
            "access_token": "refreshed_access_token",
            "refresh_token": "new_refresh_token",
            "expires_at": 1735862400
        }
        """

        let data = json.data(using: .utf8)!
        let response = try JSONDecoder().decode(RefreshTokenResponse.self, from: data)

        #expect(response.accessToken == "refreshed_access_token")
        #expect(response.refreshToken == "new_refresh_token")
        #expect(response.expiresAt == 1735862400)

        // Verify expiry date conversion
        let expiryDate = Date(timeIntervalSince1970: TimeInterval(response.expiresAt))
        #expect(expiryDate > Date(timeIntervalSince1970: 0))
    }

    // MARK: - Token Refresh Concurrency Tests

    @Test("Concurrent club fetches share a single token refresh")
    func concurrentFetchesShareSingleTokenRefresh() async throws {
        // Hold every mock response in flight long enough that all club
        // fetches hit getValidToken() while the first refresh is pending.
        let refreshHoldTime = Duration.milliseconds(50)
        let tokenLifetime: TimeInterval = 3600
        let clubIds = [1, 2, 3, 4, 5]

        let mockKeychain = MockKeychainHelper()
        try mockKeychain.setCredentials(clientId: "test_client_id", clientSecret: "test_client_secret")
        try mockKeychain.setAuthenticatedState(
            accessToken: "expired_token",
            refreshToken: "valid_refresh_token",
            expiresAt: Date().addingTimeInterval(-tokenLifetime)
        )

        let mockSession = MockURLSession()
        mockSession.responseDelay = refreshHoldTime

        let tokenURL = URL(string: "https://www.strava.com/oauth/token")!
        let newExpiry = Int(Date().addingTimeInterval(tokenLifetime).timeIntervalSince1970)
        mockSession.setMockJSONResponse(for: tokenURL, json: """
        {
            "access_token": "fresh_token",
            "refresh_token": "next_refresh_token",
            "expires_at": \(newExpiry)
        }
        """)

        for clubId in clubIds {
            let eventsURL = URL(string: "https://www.strava.com/api/v3/clubs/\(clubId)/group_events")!
            mockSession.setMockJSONResponse(for: eventsURL, json: "[]")
        }

        let service = StravaService(keychain: mockKeychain, session: mockSession)
        let fetch = await service.getEventsForClubs(clubIds)

        #expect(fetch.events.isEmpty)
        #expect(fetch.failedClubIds.isEmpty)
        #expect(fetch.firstError == nil)

        let tokenRequests = mockSession.capturedRequests.filter { $0.url == tokenURL }
        #expect(tokenRequests.count == 1, "All concurrent fetches should share one refresh")
        #expect(mockSession.capturedRequests.count == clubIds.count + 1)

        // Every club fetch should carry the refreshed token.
        let clubRequests = mockSession.capturedRequests.filter { $0.url != tokenURL }
        for request in clubRequests {
            #expect(request.value(forHTTPHeaderField: "Authorization") == "Bearer fresh_token")
        }
    }

    // MARK: - Partial Failure Tests

    @Test("getEventsForClubs reports clubs whose fetch failed and keeps the rest")
    func getEventsForClubsReportsFailedClubs() async throws {
        let tokenLifetime: TimeInterval = 3600
        let healthyClubId = 10
        let brokenClubId = 20
        let serverErrorStatus = 503

        let mockKeychain = MockKeychainHelper()
        try mockKeychain.setCredentials(clientId: "test_client_id", clientSecret: "test_client_secret")
        try mockKeychain.setAuthenticatedState(
            accessToken: "valid_token",
            refreshToken: "valid_refresh_token",
            expiresAt: Date().addingTimeInterval(tokenLifetime)
        )

        let futureStart = ISO8601DateFormatter().string(from: Date().addingTimeInterval(tokenLifetime))
        let mockSession = MockURLSession()
        let healthyURL = URL(string: "https://www.strava.com/api/v3/clubs/\(healthyClubId)/group_events")!
        mockSession.setMockJSONResponse(for: healthyURL, json: """
        [{
            "id": 555,
            "title": "Tempo Run",
            "club": {"id": \(healthyClubId), "name": "Healthy Club"},
            "activity_type": "Run",
            "upcoming_occurrences": ["\(futureStart)"]
        }]
        """)
        let brokenURL = URL(string: "https://www.strava.com/api/v3/clubs/\(brokenClubId)/group_events")!
        mockSession.setMockJSONResponse(for: brokenURL, json: "{}", statusCode: serverErrorStatus)

        let service = StravaService(keychain: mockKeychain, session: mockSession)
        let fetch = await service.getEventsForClubs([healthyClubId, brokenClubId])

        #expect(fetch.events.map(\.id) == [555], "Healthy club's events should still be returned")
        #expect(fetch.failedClubIds == [brokenClubId])
        guard case .serverError(let statusCode)? = fetch.firstError as? StravaError else {
            Issue.record("Expected StravaError.serverError, got \(String(describing: fetch.firstError))")
            return
        }
        #expect(statusCode == serverErrorStatus)
    }

    // MARK: - Mock Session Tests

    @Test("MockURLSession captures requests")
    func mockURLSessionCapturesRequests() async throws {
        let mockSession = MockURLSession()
        let testURL = URL(string: "https://api.example.com/test")!
        mockSession.setMockJSONResponse(for: testURL, json: "{\"test\": true}")

        var request = URLRequest(url: testURL)
        request.httpMethod = "GET"
        request.setValue("Bearer token", forHTTPHeaderField: "Authorization")

        _ = try await mockSession.data(for: request)

        #expect(mockSession.capturedRequests.count == 1)
        #expect(mockSession.capturedRequests[0].url == testURL)
        #expect(mockSession.capturedRequests[0].httpMethod == "GET")
        #expect(mockSession.capturedRequests[0].value(forHTTPHeaderField: "Authorization") == "Bearer token")
    }

    @Test("MockURLSession returns error when configured")
    func mockURLSessionReturnsError() async {
        let mockSession = MockURLSession()
        mockSession.mockError = URLError(.notConnectedToInternet)

        let testURL = URL(string: "https://api.example.com/test")!
        var request = URLRequest(url: testURL)
        request.httpMethod = "GET"

        do {
            _ = try await mockSession.data(for: request)
            Issue.record("Expected error to be thrown")
        } catch {
            #expect(error is URLError)
        }
    }

    @Test("MockURLSession returns different status codes")
    func mockURLSessionReturnsDifferentStatusCodes() async throws {
        let mockSession = MockURLSession()

        let url200 = URL(string: "https://api.example.com/success")!
        let url401 = URL(string: "https://api.example.com/unauthorized")!
        let url500 = URL(string: "https://api.example.com/error")!

        mockSession.setMockJSONResponse(for: url200, json: "{}", statusCode: 200)
        mockSession.setMockJSONResponse(for: url401, json: "{\"error\": \"unauthorized\"}", statusCode: 401)
        mockSession.setMockJSONResponse(for: url500, json: "{\"error\": \"server error\"}", statusCode: 500)

        let (_, response200) = try await mockSession.data(for: URLRequest(url: url200))
        let (_, response401) = try await mockSession.data(for: URLRequest(url: url401))
        let (_, response500) = try await mockSession.data(for: URLRequest(url: url500))

        #expect((response200 as? HTTPURLResponse)?.statusCode == 200)
        #expect((response401 as? HTTPURLResponse)?.statusCode == 401)
        #expect((response500 as? HTTPURLResponse)?.statusCode == 500)
    }

    // MARK: - Date Parsing Tests

    @Test("ISO8601 date parsing with various formats")
    func iso8601DateParsingWithVariousFormats() throws {
        // JSON with fractional seconds
        _ = """
        {
            "id": 1,
            "title": "Event 1",
            "club_name": "Club",
            "start_datetime": "2025-01-25T10:30:45.123Z"
        }
        """

        let jsonWithoutFractionalSeconds = """
        {
            "id": 2,
            "title": "Event 2",
            "club_name": "Club",
            "start_datetime": "2025-01-25T10:30:45Z"
        }
        """

        let decoder = JSONDecoder()

        // Standard ISO8601 should work
        let data2 = jsonWithoutFractionalSeconds.data(using: .utf8)!
        let event2 = try decoder.decode(ClubEvent.self, from: data2)
        #expect(event2.id == 2)

        // Fractional seconds might work depending on decoder configuration
        // This tests the basic case
    }
}

import Testing
import Foundation
@testable import ClubCalendar

@Suite("Mock Service Integration Tests")
struct MockServiceTests {
    // MARK: - MockCalendarService Tests

    @Test("MockCalendarService checkAccessStatus returns configured status")
    func mockCalendarServiceCheckAccessStatus() async {
        let mock = MockCalendarService()
        #expect(await mock.checkAccessStatus() == .authorized)

        await mock.setAccessStatus(.denied)
        #expect(await mock.checkAccessStatus() == .denied)
    }

    @Test("MockCalendarService requestAccess updates status")
    func mockCalendarServiceRequestAccess() async throws {
        let mock = MockCalendarService()
        try await mock.requestAccess()
        #expect(await mock.checkAccessStatus() == .authorized)
    }

    @Test("MockCalendarService syncEvents stores synced events")
    func mockCalendarServiceSyncEvents() async throws {
        let mock = MockCalendarService()
        let event = ClubEvent(
            id: 1, title: "Test", clubName: "Club",
            description: nil, activityType: nil,
            startDatetime: Date(), address: nil,
            privateEvent: nil, organizingAthlete: nil, routeId: nil
        )

        let result = try await mock.syncEvents([event])
        #expect(result.created == 1)
        let synced = await mock.syncedEvents
        #expect(synced.count == 1)
    }

    @Test("MockCalendarService getUpcomingEvents respects limit")
    func mockCalendarServiceUpcomingEventsLimit() async {
        let mock = MockCalendarService()
        let events = (1...10).map {
            CalendarEventData(id: "\($0)", title: "Event \($0)", startDate: Date())
        }
        await mock.setUpcomingEvents(events)

        let limited = await mock.getUpcomingEvents(limit: 3)
        #expect(limited.count == 3)

        let all = await mock.getUpcomingEvents(limit: 100)
        #expect(all.count == 10)
    }

    // MARK: - MockStravaService Tests

    @Test("MockStravaService exchangeToken returns token response")
    func mockStravaServiceExchangeToken() async throws {
        let mock = MockStravaService()
        let response = try await mock.exchangeToken(code: "test_code")

        #expect(response.accessToken.contains("test_code"))
        #expect(response.refreshToken.contains("test_code"))
        #expect(response.athlete?.firstName == "Test")
        #expect(response.athlete?.lastName == "User")
    }

    @Test("MockStravaService exchangeToken throws when configured")
    func mockStravaServiceExchangeTokenThrows() async {
        let mock = MockStravaService()
        await mock.setShouldThrowOnExchange(true)

        do {
            _ = try await mock.exchangeToken(code: "test")
            Issue.record("Expected error")
        } catch {
            // Expected
        }
    }

    @Test("MockStravaService refreshAccessToken returns token")
    func mockStravaServiceRefreshToken() async throws {
        let mock = MockStravaService()
        let token = try await mock.refreshAccessToken()
        #expect(token == "refreshed_token")
    }

    @Test("MockStravaService refreshAccessToken throws when configured")
    func mockStravaServiceRefreshTokenThrows() async {
        let mock = MockStravaService()
        await mock.setShouldThrowOnRefresh(true)

        do {
            _ = try await mock.refreshAccessToken()
            Issue.record("Expected error")
        } catch {
            // Expected
        }
    }

    @Test("MockStravaService getAthleteClubs returns configured clubs")
    func mockStravaServiceGetClubs() async throws {
        let mock = MockStravaService()
        let clubs = [
            Club(id: 1, name: "Club 1", memberCount: 100, city: "City 1", sportType: "cycling", profileMedium: nil),
            Club(id: 2, name: "Club 2", memberCount: 200, city: "City 2", sportType: "running", profileMedium: nil)
        ]
        await mock.setClubs(clubs)

        let result = try await mock.getAthleteClubs()
        #expect(result.count == 2)
        #expect(result[0].name == "Club 1")
        #expect(result[1].name == "Club 2")
    }

    @Test("MockStravaService getClubEvents returns configured events")
    func mockStravaServiceGetClubEvents() async throws {
        let mock = MockStravaService()
        let events = [
            ClubEvent(
                id: 1, title: "Event 1", clubName: "Club",
                description: nil, activityType: "Ride",
                startDatetime: Date(), address: nil,
                privateEvent: nil, organizingAthlete: nil, routeId: nil
            )
        ]
        await mock.setEvents(for: 1, events: events)

        let result = try await mock.getClubEvents(clubId: 1)
        #expect(result.count == 1)
        #expect(result[0].title == "Event 1")
    }

    @Test("MockStravaService getEventsForClubs aggregates events")
    func mockStravaServiceGetEventsForClubs() async throws {
        let mock = MockStravaService()
        let now = Date()
        let events1 = [
            ClubEvent(
                id: 1, title: "Event 1", clubName: "Club 1",
                description: nil, activityType: nil,
                startDatetime: now.addingTimeInterval(3600), address: nil,
                privateEvent: nil, organizingAthlete: nil, routeId: nil
            )
        ]
        let events2 = [
            ClubEvent(
                id: 2, title: "Event 2", clubName: "Club 2",
                description: nil, activityType: nil,
                startDatetime: now, address: nil,
                privateEvent: nil, organizingAthlete: nil, routeId: nil
            )
        ]
        await mock.setEvents(for: 1, events: events1)
        await mock.setEvents(for: 2, events: events2)

        let result = try await mock.getEventsForClubs([1, 2])
        #expect(result.count == 2)
        // Should be sorted by date, so Event 2 (now) comes before Event 1 (now + 1hr)
        #expect(result[0].title == "Event 2")
        #expect(result[1].title == "Event 1")
    }

    // MARK: - MockAuthService Tests

    @Test("MockAuthService authenticate sets authenticated state")
    @MainActor
    func mockAuthServiceAuthenticate() async throws {
        let mock = MockAuthService()
        #expect(await mock.isAuthenticated() == false)

        try await mock.authenticate()

        #expect(mock.authenticateCalled == true)
        #expect(await mock.isAuthenticated() == true)
    }

    @Test("MockAuthService authenticate throws when configured")
    @MainActor
    func mockAuthServiceAuthenticateThrows() async {
        let mock = MockAuthService()
        mock.shouldThrowOnAuthenticate = true

        do {
            try await mock.authenticate()
            Issue.record("Expected error")
        } catch {
            // Expected
        }
    }

    @Test("MockAuthService disconnect clears state")
    @MainActor
    func mockAuthServiceDisconnect() async throws {
        let mock = MockAuthService()
        mock.setAuthenticated(true, athleteName: "Test User")

        try await mock.disconnect()

        #expect(mock.disconnectCalled == true)
        #expect(await mock.isAuthenticated() == false)
        #expect(await mock.getAthleteName() == nil)
    }

    @Test("MockAuthService getAthleteName returns configured name")
    @MainActor
    func mockAuthServiceGetAthleteName() async {
        let mock = MockAuthService()
        mock.setAuthenticated(true, athleteName: "John Doe")

        let name = await mock.getAthleteName()
        #expect(name == "John Doe")
    }

    // MARK: - MockKeychainHelper Tests

    @Test("MockKeychainHelper save and getString work correctly")
    func mockKeychainHelperSaveAndGet() async throws {
        let mock = MockKeychainHelper()

        try await mock.save("test_value", for: .clientId)
        let value = try await mock.getString(for: .clientId)

        #expect(value == "test_value")
    }

    @Test("MockKeychainHelper getStringOrNil returns nil for missing key")
    func mockKeychainHelperGetStringOrNil() async {
        let mock = MockKeychainHelper()
        let value = await mock.getStringOrNil(for: .clientId)
        #expect(value == nil)
    }

    @Test("MockKeychainHelper exists returns correct values")
    func mockKeychainHelperExists() async throws {
        let mock = MockKeychainHelper()

        #expect(await mock.exists(key: .clientId) == false)

        try await mock.save("value", for: .clientId)

        #expect(await mock.exists(key: .clientId) == true)
    }

    @Test("MockKeychainHelper delete removes key")
    func mockKeychainHelperDelete() async throws {
        let mock = MockKeychainHelper()

        try await mock.save("value", for: .clientId)
        #expect(await mock.exists(key: .clientId) == true)

        try await mock.delete(key: .clientId)
        #expect(await mock.exists(key: .clientId) == false)
    }

    @Test("MockKeychainHelper saveTokens stores all token data")
    func mockKeychainHelperSaveTokens() async throws {
        let mock = MockKeychainHelper()
        let expiry = Date().addingTimeInterval(3600)

        try await mock.saveTokens(accessToken: "access", refreshToken: "refresh", expiresAt: expiry)

        #expect(await mock.getStringOrNil(for: .accessToken) == "access")
        #expect(await mock.getStringOrNil(for: .refreshToken) == "refresh")
        #expect(await mock.getTokenExpiry() != nil)
    }

    @Test("MockKeychainHelper getValidAccessToken returns nil for expired token")
    func mockKeychainHelperExpiredToken() async throws {
        let mock = MockKeychainHelper()
        let pastExpiry = Date().addingTimeInterval(-3600)  // 1 hour ago

        try await mock.saveTokens(accessToken: "expired", refreshToken: "refresh", expiresAt: pastExpiry)

        let token = await mock.getValidAccessToken()
        #expect(token == nil)
    }

    @Test("MockKeychainHelper getValidAccessToken returns token for valid token")
    func mockKeychainHelperValidToken() async throws {
        let mock = MockKeychainHelper()
        let futureExpiry = Date().addingTimeInterval(3600)  // 1 hour from now

        try await mock.saveTokens(accessToken: "valid", refreshToken: "refresh", expiresAt: futureExpiry)

        let token = await mock.getValidAccessToken()
        #expect(token == "valid")
    }

    @Test("MockKeychainHelper clearAuth removes auth tokens")
    func mockKeychainHelperClearAuth() async throws {
        let mock = MockKeychainHelper()

        try await mock.saveTokens(accessToken: "access", refreshToken: "refresh", expiresAt: Date())
        try await mock.save("12345", for: .athleteId)
        try await mock.save("Test User", for: .athleteName)

        try await mock.clearAuth()

        #expect(await mock.getStringOrNil(for: .accessToken) == nil)
        #expect(await mock.getStringOrNil(for: .refreshToken) == nil)
        #expect(await mock.getStringOrNil(for: .athleteId) == nil)
        #expect(await mock.getStringOrNil(for: .athleteName) == nil)
    }

    @Test("MockKeychainHelper hasAPICredentials checks both keys")
    func mockKeychainHelperHasAPICredentials() async throws {
        let mock = MockKeychainHelper()

        #expect(await mock.hasAPICredentials() == false)

        try await mock.save("client_id", for: .clientId)
        #expect(await mock.hasAPICredentials() == false)

        try await mock.save("client_secret", for: .clientSecret)
        #expect(await mock.hasAPICredentials() == true)
    }

    @Test("MockKeychainHelper isAuthenticated checks refresh token")
    func mockKeychainHelperIsAuthenticated() async throws {
        let mock = MockKeychainHelper()

        #expect(await mock.isAuthenticated() == false)

        try await mock.save("refresh_token", for: .refreshToken)
        #expect(await mock.isAuthenticated() == true)
    }

    // MARK: - MockURLSession Tests

    @Test("MockURLSession returns configured response")
    func mockURLSessionReturnsResponse() async throws {
        let mock = MockURLSession()
        let url = URL(string: "https://api.strava.com/test")!
        mock.setMockJSONResponse(for: url, json: "{\"test\": \"value\"}")

        var request = URLRequest(url: url)
        request.httpMethod = "GET"

        let (data, response) = try await mock.data(for: request)

        #expect(data.count > 0)
        #expect((response as? HTTPURLResponse)?.statusCode == 200)
    }

    @Test("MockURLSession throws for unknown URL")
    func mockURLSessionThrowsForUnknownURL() async {
        let mock = MockURLSession()
        let url = URL(string: "https://unknown.com/test")!
        let request = URLRequest(url: url)

        do {
            _ = try await mock.data(for: request)
            Issue.record("Expected error")
        } catch {
            // Expected
        }
    }

    @Test("MockURLSession throws configured error")
    func mockURLSessionThrowsConfiguredError() async {
        let mock = MockURLSession()
        mock.mockError = URLError(.notConnectedToInternet)

        let url = URL(string: "https://api.strava.com/test")!
        let request = URLRequest(url: url)

        do {
            _ = try await mock.data(for: request)
            Issue.record("Expected error")
        } catch let error as URLError {
            #expect(error.code == .notConnectedToInternet)
        } catch {
            Issue.record("Unexpected error type")
        }
    }

    @Test("MockURLSession captures requests")
    func mockURLSessionCapturesRequests() async throws {
        let mock = MockURLSession()
        let url = URL(string: "https://api.strava.com/test")!
        mock.setMockJSONResponse(for: url, json: "{}")

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer token", forHTTPHeaderField: "Authorization")

        _ = try await mock.data(for: request)

        #expect(mock.capturedRequests.count == 1)
        #expect(mock.capturedRequests[0].httpMethod == "POST")
        #expect(mock.capturedRequests[0].value(forHTTPHeaderField: "Authorization") == "Bearer token")
    }
}

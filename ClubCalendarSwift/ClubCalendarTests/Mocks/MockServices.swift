import Foundation
@testable import ClubCalendar

// MARK: - Mock Calendar Service

/// Mock implementation of CalendarServiceProtocol for testing.
actor MockCalendarService: CalendarServiceProtocol {
    var accessStatus: CalendarAccessStatus = .authorized
    var shouldThrowOnRequest = false
    var shouldThrowOnSync = false
    var upcomingEvents: [CalendarEventData] = []
    var availableCalendars: [String] = ["Club Calendar", "Personal", "Work"]
    var syncedEvents: [ClubEvent] = []
    var lastSyncResult = SyncResult(created: 0, updated: 0, cancelled: 0)

    func checkAccessStatus() -> CalendarAccessStatus {
        accessStatus
    }

    func requestAccess() async throws {
        if shouldThrowOnRequest {
            throw CalendarError.accessDenied
        }
        accessStatus = .authorized
    }

    func syncEvents(_ clubEvents: [ClubEvent]) async throws -> SyncResult {
        if shouldThrowOnSync {
            throw CalendarError.eventCreationFailed
        }
        syncedEvents = clubEvents
        return SyncResult(created: clubEvents.count, updated: 0, cancelled: 0)
    }

    func getUpcomingEvents(limit: Int) -> [CalendarEventData] {
        Array(upcomingEvents.prefix(limit))
    }

    func getAvailableCalendars() -> [String] {
        availableCalendars
    }

    // Test helpers
    func setUpcomingEvents(_ events: [CalendarEventData]) {
        upcomingEvents = events
    }

    func setSyncResult(_ result: SyncResult) {
        lastSyncResult = result
    }

    func setAccessStatus(_ status: CalendarAccessStatus) {
        accessStatus = status
    }

    func setShouldThrowOnRequest(_ value: Bool) {
        shouldThrowOnRequest = value
    }

    func setShouldThrowOnSync(_ value: Bool) {
        shouldThrowOnSync = value
    }
}

// MARK: - Mock Strava Service

/// Mock implementation of StravaServiceProtocol for testing.
actor MockStravaService: StravaServiceProtocol {
    var clubs: [Club] = []
    var eventsByClubId: [Int: [ClubEvent]] = [:]
    var shouldThrowOnExchange = false
    var shouldThrowOnRefresh = false
    var shouldThrowOnGetClubs = false
    var shouldThrowOnGetEvents = false
    var exchangeTokenResult: TokenResponse?
    var refreshedAccessToken = "refreshed_token"

    func exchangeToken(code: String) async throws -> TokenResponse {
        if shouldThrowOnExchange {
            throw StravaError.invalidCredentials
        }
        return exchangeTokenResult ?? TokenResponse(
            accessToken: "access_\(code)",
            refreshToken: "refresh_\(code)",
            expiresAt: Int(Date().addingTimeInterval(3600).timeIntervalSince1970),
            athlete: TokenAthlete(id: 12345, firstName: "Test", lastName: "User")
        )
    }

    func refreshAccessToken() async throws -> String {
        if shouldThrowOnRefresh {
            throw StravaError.noRefreshToken
        }
        return refreshedAccessToken
    }

    func getAthleteClubs() async throws -> [Club] {
        if shouldThrowOnGetClubs {
            throw StravaError.authRequired
        }
        return clubs
    }

    func getClubEvents(clubId: Int) async throws -> [ClubEvent] {
        if shouldThrowOnGetEvents {
            throw StravaError.serverError(statusCode: 500)
        }
        return eventsByClubId[clubId] ?? []
    }

    func getEventsForClubs(_ clubIds: [Int]) async throws -> [ClubEvent] {
        var allEvents: [ClubEvent] = []
        for clubId in clubIds {
            let events = try await getClubEvents(clubId: clubId)
            allEvents.append(contentsOf: events)
        }
        return allEvents.sorted { $0.startDatetime < $1.startDatetime }
    }

    // Test helpers
    func setClubs(_ clubs: [Club]) {
        self.clubs = clubs
    }

    func setEvents(for clubId: Int, events: [ClubEvent]) {
        eventsByClubId[clubId] = events
    }

    func setShouldThrowOnExchange(_ value: Bool) {
        shouldThrowOnExchange = value
    }

    func setShouldThrowOnRefresh(_ value: Bool) {
        shouldThrowOnRefresh = value
    }

    func setShouldThrowOnGetClubs(_ value: Bool) {
        shouldThrowOnGetClubs = value
    }

    func setShouldThrowOnGetEvents(_ value: Bool) {
        shouldThrowOnGetEvents = value
    }
}

// MARK: - Mock Auth Service

/// Mock implementation of AuthServiceProtocol for testing.
@MainActor
final class MockAuthService: AuthServiceProtocol, @unchecked Sendable {
    var isAuthenticatedValue = false
    var athleteName: String?
    var shouldThrowOnAuthenticate = false
    var shouldThrowOnDisconnect = false
    var authenticateCalled = false
    var disconnectCalled = false

    func authenticate() async throws {
        authenticateCalled = true
        if shouldThrowOnAuthenticate {
            throw AuthError.cancelled
        }
        isAuthenticatedValue = true
    }

    func disconnect() async throws {
        disconnectCalled = true
        if shouldThrowOnDisconnect {
            throw AuthError.noCredentials
        }
        isAuthenticatedValue = false
        athleteName = nil
    }

    func isAuthenticated() async -> Bool {
        isAuthenticatedValue
    }

    func getAthleteName() async -> String? {
        athleteName
    }

    // Test helpers
    func setAuthenticated(_ value: Bool, athleteName: String? = nil) {
        isAuthenticatedValue = value
        self.athleteName = athleteName
    }
}

import Foundation

// MARK: - Keychain Protocol

/// Protocol for keychain operations, enabling testability.
protocol KeychainHelperProtocol: Sendable {
    func save(_ value: String, for key: KeychainKey) async throws
    func getString(for key: KeychainKey) async throws -> String
    func getStringOrNil(for key: KeychainKey) async -> String?
    func save(_ data: Data, for key: KeychainKey) async throws
    func getData(for key: KeychainKey) async throws -> Data
    func delete(key: KeychainKey) async throws
    func exists(key: KeychainKey) async -> Bool
    func saveTokens(accessToken: String, refreshToken: String, expiresAt: Date) async throws
    func getValidAccessToken() async -> String?
    func getTokenExpiry() async -> Date?
    func clearAuth() async throws
    func clearAll() async throws
    func hasAPICredentials() async -> Bool
    func isAuthenticated() async -> Bool
}

// MARK: - Calendar Service Protocol

/// Protocol for calendar operations, enabling testability.
protocol CalendarServiceProtocol: Sendable {
    func checkAccessStatus() async -> CalendarAccessStatus
    func requestAccess() async throws
    func syncEvents(_ clubEvents: [ClubEvent]) async throws -> SyncResult
    func getUpcomingEvents(limit: Int) async -> [CalendarEventData]
    func getAvailableCalendars() async -> [String]
}

// MARK: - Strava Service Protocol

/// Protocol for Strava API operations, enabling testability.
protocol StravaServiceProtocol: Sendable {
    func exchangeToken(code: String) async throws -> TokenResponse
    func refreshAccessToken() async throws -> String
    func getAthleteClubs() async throws -> [Club]
    func getClubEvents(clubId: Int) async throws -> [ClubEvent]
    func getEventsForClubs(_ clubIds: [Int]) async throws -> [ClubEvent]
}

// MARK: - Auth Service Protocol

/// Protocol for authentication operations, enabling testability.
@MainActor
protocol AuthServiceProtocol: Sendable {
    func authenticate() async throws
    func disconnect() async throws
    func isAuthenticated() async -> Bool
    func getAthleteName() async -> String?
}

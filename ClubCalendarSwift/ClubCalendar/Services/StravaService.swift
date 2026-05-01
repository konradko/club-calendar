import Foundation
import os

/// Errors from Strava API operations.
enum StravaError: Error, LocalizedError, Sendable {
    case authRequired
    case invalidCredentials
    case rateLimited(resetTime: Date?)
    case networkError(underlying: Error)
    case invalidResponse
    case serverError(statusCode: Int)
    case decodingError(underlying: Error)
    case noRefreshToken

    var errorDescription: String? {
        switch self {
        case .authRequired:
            return "Authentication required. Please connect to Strava."
        case .invalidCredentials:
            return "Invalid API credentials."
        case .rateLimited(let resetTime):
            if let time = resetTime {
                let formatter = DateFormatter()
                formatter.timeStyle = .short
                return "Rate limited. Try again after \(formatter.string(from: time))."
            }
            return "Rate limited. Please try again later."
        case .networkError(let error):
            return "Network error: \(error.localizedDescription)"
        case .invalidResponse:
            return "Invalid response from Strava."
        case .serverError(let code):
            return "Server error (HTTP \(code))."
        case .decodingError(let error):
            return "Failed to decode response: \(error.localizedDescription)"
        case .noRefreshToken:
            return "No refresh token available. Please reconnect to Strava."
        }
    }
}

/// Protocol for URL session operations (for testing).
protocol URLSessionProtocol: Sendable {
    func data(for request: URLRequest) async throws -> (Data, URLResponse)
}

extension URLSession: URLSessionProtocol {}

/// Strava API client.
actor StravaService: StravaServiceProtocol {
    private let baseURL = URL(string: "https://www.strava.com/api/v3")!
    private let oauthURL = URL(string: "https://www.strava.com/oauth")!
    private let keychain: KeychainHelper
    private let session: URLSessionProtocol
    private let decoder: JSONDecoder

    init(keychain: KeychainHelper = .shared, session: URLSessionProtocol = URLSession.shared) {
        self.keychain = keychain
        self.session = session
        self.decoder = JSONDecoder()
    }

    // MARK: - Token Management

    /// Exchanges an authorization code for access/refresh tokens.
    func exchangeToken(code: String) async throws -> TokenResponse {
        Logger.strava.info("Exchanging authorization code for tokens")
        FileLog.write("Exchanging authorization code for tokens", category: "strava")

        guard let clientId = await keychain.getStringOrNil(for: .clientId),
              let clientSecret = await keychain.getStringOrNil(for: .clientSecret) else {
            Logger.strava.error("No API credentials found in keychain")
            FileLog.write("No API credentials found in keychain", level: "ERROR", category: "strava")
            throw StravaError.invalidCredentials
        }

        let url = oauthURL.appendingPathComponent("token")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")

        let body = [
            "client_id": clientId,
            "client_secret": clientSecret,
            "code": code,
            "grant_type": "authorization_code"
        ]
        request.httpBody = body.map { "\($0)=\($1)" }.joined(separator: "&").data(using: .utf8)

        let (data, response) = try await performRequest(request)
        try validateResponse(response)

        let tokenResponse = try decoder.decode(TokenResponse.self, from: data)

        // Save tokens and athlete info
        try await keychain.saveTokens(
            accessToken: tokenResponse.accessToken,
            refreshToken: tokenResponse.refreshToken,
            expiresAt: Date(timeIntervalSince1970: TimeInterval(tokenResponse.expiresAt))
        )

        if let athlete = tokenResponse.athlete {
            try await keychain.save(String(athlete.id), for: .athleteId)
            try await keychain.save(athlete.fullName, for: .athleteName)
            Logger.strava.info("Token exchange successful, athlete: \(athlete.fullName)")
            FileLog.write("Token exchange successful, athlete: \(athlete.fullName)", category: "strava")
        } else {
            Logger.strava.info("Token exchange successful")
            FileLog.write("Token exchange successful", category: "strava")
        }

        return tokenResponse
    }

    /// Refreshes the access token using the refresh token.
    func refreshAccessToken() async throws -> String {
        Logger.strava.info("Refreshing access token")
        FileLog.write("Refreshing access token", category: "strava")

        guard let refreshToken = await keychain.getStringOrNil(for: .refreshToken) else {
            Logger.strava.error("No refresh token available")
            FileLog.write("No refresh token available", level: "ERROR", category: "strava")
            throw StravaError.noRefreshToken
        }

        guard let clientId = await keychain.getStringOrNil(for: .clientId),
              let clientSecret = await keychain.getStringOrNil(for: .clientSecret) else {
            Logger.strava.error("No API credentials for token refresh")
            FileLog.write("No API credentials for token refresh", level: "ERROR", category: "strava")
            throw StravaError.invalidCredentials
        }

        let url = oauthURL.appendingPathComponent("token")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")

        let body = [
            "client_id": clientId,
            "client_secret": clientSecret,
            "refresh_token": refreshToken,
            "grant_type": "refresh_token"
        ]
        request.httpBody = body.map { "\($0)=\($1)" }.joined(separator: "&").data(using: .utf8)

        let (data, response) = try await performRequest(request)
        try validateResponse(response)

        let tokenResponse = try decoder.decode(RefreshTokenResponse.self, from: data)

        try await keychain.saveTokens(
            accessToken: tokenResponse.accessToken,
            refreshToken: tokenResponse.refreshToken,
            expiresAt: Date(timeIntervalSince1970: TimeInterval(tokenResponse.expiresAt))
        )

        Logger.strava.info("Access token refreshed successfully")
        FileLog.write("Access token refreshed successfully", category: "strava")
        return tokenResponse.accessToken
    }

    /// Gets a valid access token, refreshing if necessary.
    private func getValidToken() async throws -> String {
        if let token = await keychain.getValidAccessToken() {
            return token
        }
        return try await refreshAccessToken()
    }

    // MARK: - API Methods

    /// Fetches all clubs for the authenticated athlete.
    func getAthleteClubs() async throws -> [Club] {
        Logger.strava.info("Fetching athlete clubs")
        FileLog.write("GET /athlete/clubs", category: "strava")
        let url = baseURL.appendingPathComponent("athlete/clubs")
        let clubs: [Club] = try await authenticatedRequest(url: url)
        Logger.strava.info("Fetched \(clubs.count) club(s)")
        FileLog.write("Fetched \(clubs.count) club(s)", category: "strava")
        return clubs
    }

    /// Fetches events for a specific club.
    func getClubEvents(clubId: Int) async throws -> [ClubEvent] {
        Logger.strava.debug("Fetching events for club \(clubId)")
        FileLog.write("GET /clubs/\(clubId)/group_events", category: "strava")
        let url = baseURL.appendingPathComponent("clubs/\(clubId)/group_events")
        let events: [ClubEvent] = try await authenticatedRequest(url: url)

        // Strava's `upcoming_occurrences` can include today's already-passed
        // start time for recurring events; drop anything that has already
        // happened so it doesn't get (re-)created in the calendar.
        let now = Date()
        let upcoming = events.filter { $0.startDatetime >= now }

        Logger.strava.debug("Club \(clubId): \(upcoming.count) upcoming event(s) (\(events.count - upcoming.count) past skipped)")
        FileLog.write("Club \(clubId): \(upcoming.count) upcoming event(s) (\(events.count - upcoming.count) past skipped)", category: "strava")
        return upcoming
    }

    /// Fetches events for multiple clubs.
    func getEventsForClubs(_ clubIds: [Int]) async throws -> [ClubEvent] {
        var allEvents: [ClubEvent] = []

        for clubId in clubIds {
            do {
                let events = try await getClubEvents(clubId: clubId)
                allEvents.append(contentsOf: events)
            } catch {
                Logger.strava.error("Failed to fetch events for club \(clubId): \(error.localizedDescription)")
                FileLog.write("Failed to fetch events for club \(clubId): \(error.localizedDescription)", level: "ERROR", category: "strava")
            }
        }

        // Sort by start date
        return allEvents.sorted { $0.startDatetime < $1.startDatetime }
    }

    // MARK: - Request Helpers

    private func authenticatedRequest<T: Decodable>(url: URL) async throws -> T {
        let token = try await getValidToken()

        var request = URLRequest(url: url)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Accept")

        let (data, response) = try await performRequest(request)
        try validateResponse(response)

        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            let bodyPreview = String(data: data.prefix(1000), encoding: .utf8) ?? "<binary>"
            Logger.strava.error("Decoding failed for \(url.lastPathComponent): \(error.localizedDescription)")
            FileLog.write("Decoding failed for \(url.path): \(error)", level: "ERROR", category: "strava")
            FileLog.write("Response body: \(bodyPreview)", level: "DEBUG", category: "strava")
            throw StravaError.decodingError(underlying: error)
        }
    }

    private func performRequest(_ request: URLRequest) async throws -> (Data, URLResponse) {
        do {
            return try await session.data(for: request)
        } catch {
            Logger.strava.error("Network request failed: \(error.localizedDescription)")
            FileLog.write("Network request failed: \(request.url?.absoluteString ?? "unknown") - \(error.localizedDescription)", level: "ERROR", category: "strava")
            throw StravaError.networkError(underlying: error)
        }
    }

    private func validateResponse(_ response: URLResponse) throws {
        guard let httpResponse = response as? HTTPURLResponse else {
            throw StravaError.invalidResponse
        }

        let statusCode = httpResponse.statusCode
        Logger.strava.debug("HTTP \(statusCode)")
        FileLog.write("HTTP \(statusCode)", level: "DEBUG", category: "strava")

        switch statusCode {
        case 200...299:
            return
        case 401:
            Logger.strava.error("Auth required (HTTP 401)")
            FileLog.write("Auth required (HTTP 401)", level: "ERROR", category: "strava")
            throw StravaError.authRequired
        case 429:
            let resetTime = httpResponse.value(forHTTPHeaderField: "X-RateLimit-Reset")
                .flatMap { Double($0) }
                .map { Date(timeIntervalSince1970: $0) }
            Logger.strava.error("Rate limited (HTTP 429)")
            FileLog.write("Rate limited (HTTP 429)", level: "ERROR", category: "strava")
            throw StravaError.rateLimited(resetTime: resetTime)
        default:
            Logger.strava.error("Server error (HTTP \(statusCode))")
            FileLog.write("Server error (HTTP \(statusCode))", level: "ERROR", category: "strava")
            throw StravaError.serverError(statusCode: statusCode)
        }
    }
}

// MARK: - Response Types

struct TokenResponse: Codable, Sendable {
    let accessToken: String
    let refreshToken: String
    let expiresAt: Int
    let athlete: TokenAthlete?

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case expiresAt = "expires_at"
        case athlete
    }
}

struct RefreshTokenResponse: Codable, Sendable {
    let accessToken: String
    let refreshToken: String
    let expiresAt: Int

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case expiresAt = "expires_at"
    }
}

struct TokenAthlete: Codable, Sendable {
    let id: Int
    let firstName: String?
    let lastName: String?

    enum CodingKeys: String, CodingKey {
        case id
        case firstName = "firstname"
        case lastName = "lastname"
    }

    var fullName: String {
        [firstName, lastName].compactMap { $0 }.joined(separator: " ")
    }
}

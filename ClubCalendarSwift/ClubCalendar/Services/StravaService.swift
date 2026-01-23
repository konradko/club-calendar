import Foundation

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

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let dateString = try container.decode(String.self)

            // Try ISO8601 with fractional seconds
            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            if let date = formatter.date(from: dateString) {
                return date
            }

            // Try ISO8601 without fractional seconds
            formatter.formatOptions = [.withInternetDateTime]
            if let date = formatter.date(from: dateString) {
                return date
            }

            throw DecodingError.dataCorruptedError(
                in: container,
                debugDescription: "Cannot decode date: \(dateString)"
            )
        }
        self.decoder = decoder
    }

    // MARK: - Token Management

    /// Exchanges an authorization code for access/refresh tokens.
    func exchangeToken(code: String) async throws -> TokenResponse {
        guard let clientId = await keychain.getStringOrNil(for: .clientId),
              let clientSecret = await keychain.getStringOrNil(for: .clientSecret) else {
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
        }

        return tokenResponse
    }

    /// Refreshes the access token using the refresh token.
    func refreshAccessToken() async throws -> String {
        guard let refreshToken = await keychain.getStringOrNil(for: .refreshToken) else {
            throw StravaError.noRefreshToken
        }

        guard let clientId = await keychain.getStringOrNil(for: .clientId),
              let clientSecret = await keychain.getStringOrNil(for: .clientSecret) else {
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
        let url = baseURL.appendingPathComponent("athlete/clubs")
        return try await authenticatedRequest(url: url)
    }

    /// Fetches events for a specific club.
    func getClubEvents(clubId: Int) async throws -> [ClubEvent] {
        let url = baseURL.appendingPathComponent("clubs/\(clubId)/group_events")
        return try await authenticatedRequest(url: url)
    }

    /// Fetches events for multiple clubs.
    func getEventsForClubs(_ clubIds: [Int]) async throws -> [ClubEvent] {
        var allEvents: [ClubEvent] = []

        for clubId in clubIds {
            do {
                let events = try await getClubEvents(clubId: clubId)
                allEvents.append(contentsOf: events)
            } catch {
                // Log but continue with other clubs
                print("Failed to fetch events for club \(clubId): \(error)")
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
            throw StravaError.decodingError(underlying: error)
        }
    }

    private func performRequest(_ request: URLRequest) async throws -> (Data, URLResponse) {
        do {
            return try await session.data(for: request)
        } catch {
            throw StravaError.networkError(underlying: error)
        }
    }

    private func validateResponse(_ response: URLResponse) throws {
        guard let httpResponse = response as? HTTPURLResponse else {
            throw StravaError.invalidResponse
        }

        switch httpResponse.statusCode {
        case 200...299:
            return
        case 401:
            throw StravaError.authRequired
        case 429:
            let resetTime = httpResponse.value(forHTTPHeaderField: "X-RateLimit-Reset")
                .flatMap { Double($0) }
                .map { Date(timeIntervalSince1970: $0) }
            throw StravaError.rateLimited(resetTime: resetTime)
        default:
            throw StravaError.serverError(statusCode: httpResponse.statusCode)
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

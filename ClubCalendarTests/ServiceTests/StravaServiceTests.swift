import Testing
import Foundation
@testable import ClubCalendar

@Suite("StravaService")
struct StravaServiceTests {
    @Test("Token response decodes correctly")
    func tokenResponseDecodes() throws {
        let json = """
        {
            "access_token": "abc123",
            "refresh_token": "xyz789",
            "expires_at": 1735689600,
            "athlete": {
                "id": 12345,
                "firstname": "John",
                "lastname": "Doe"
            }
        }
        """

        let data = json.data(using: .utf8)!
        let response = try JSONDecoder().decode(TokenResponse.self, from: data)

        #expect(response.accessToken == "abc123")
        #expect(response.refreshToken == "xyz789")
        #expect(response.expiresAt == 1735689600)
        #expect(response.athlete?.id == 12345)
        #expect(response.athlete?.fullName == "John Doe")
    }

    @Test("Refresh token response decodes correctly")
    func refreshTokenResponseDecodes() throws {
        let json = """
        {
            "access_token": "new_token",
            "refresh_token": "new_refresh",
            "expires_at": 1735776000
        }
        """

        let data = json.data(using: .utf8)!
        let response = try JSONDecoder().decode(RefreshTokenResponse.self, from: data)

        #expect(response.accessToken == "new_token")
        #expect(response.refreshToken == "new_refresh")
        #expect(response.expiresAt == 1735776000)
    }

    @Test("Token athlete full name concatenation")
    func tokenAthleteFullName() {
        let athlete1 = TokenAthlete(id: 1, firstName: "John", lastName: "Doe")
        #expect(athlete1.fullName == "John Doe")

        let athlete2 = TokenAthlete(id: 2, firstName: "Jane", lastName: nil)
        #expect(athlete2.fullName == "Jane")

        let athlete3 = TokenAthlete(id: 3, firstName: nil, lastName: "Smith")
        #expect(athlete3.fullName == "Smith")

        let athlete4 = TokenAthlete(id: 4, firstName: nil, lastName: nil)
        #expect(athlete4.fullName == "")
    }

    @Test("Token response without athlete")
    func tokenResponseWithoutAthlete() throws {
        let json = """
        {
            "access_token": "token_only",
            "refresh_token": "refresh_only",
            "expires_at": 1735689600
        }
        """

        let data = json.data(using: .utf8)!
        let response = try JSONDecoder().decode(TokenResponse.self, from: data)

        #expect(response.athlete == nil)
        #expect(response.accessToken == "token_only")
    }

    @Test("Strava error descriptions are meaningful")
    func stravaErrorDescriptions() {
        let errors: [StravaError] = [
            .authRequired,
            .invalidCredentials,
            .rateLimited(resetTime: Date()),
            .rateLimited(resetTime: nil),
            .networkError(underlying: URLError(.notConnectedToInternet)),
            .invalidResponse,
            .serverError(statusCode: 500),
            .decodingError(underlying: DecodingError.dataCorrupted(.init(codingPath: [], debugDescription: "test"))),
            .noRefreshToken
        ]

        for error in errors {
            #expect(error.errorDescription != nil)
            #expect(!error.errorDescription!.isEmpty)
        }
    }

    // MARK: - TokenAthlete Additional Tests

    @Test("TokenAthlete encodes and decodes correctly")
    func tokenAthleteRoundTrip() throws {
        let original = TokenAthlete(id: 12345, firstName: "Test", lastName: "User")

        let encoder = JSONEncoder()
        let decoder = JSONDecoder()

        let data = try encoder.encode(original)
        let decoded = try decoder.decode(TokenAthlete.self, from: data)

        #expect(decoded.id == original.id)
        #expect(decoded.firstName == original.firstName)
        #expect(decoded.lastName == original.lastName)
        #expect(decoded.fullName == original.fullName)
    }

    @Test("TokenAthlete with nil names encodes and decodes")
    func tokenAthleteWithNilNamesRoundTrip() throws {
        let original = TokenAthlete(id: 1, firstName: nil, lastName: nil)

        let encoder = JSONEncoder()
        let decoder = JSONDecoder()

        let data = try encoder.encode(original)
        let decoded = try decoder.decode(TokenAthlete.self, from: data)

        #expect(decoded.id == original.id)
        #expect(decoded.firstName == nil)
        #expect(decoded.lastName == nil)
        #expect(decoded.fullName == "")
    }

    @Test("TokenAthlete fullName with whitespace handling")
    func tokenAthleteFullNameWhitespace() {
        let athlete1 = TokenAthlete(id: 1, firstName: "John", lastName: "")
        #expect(athlete1.fullName == "John ")

        let athlete2 = TokenAthlete(id: 2, firstName: "", lastName: "Doe")
        #expect(athlete2.fullName == " Doe")
    }

    // MARK: - TokenResponse Additional Tests

    @Test("TokenResponse encodes and decodes correctly")
    func tokenResponseRoundTrip() throws {
        let original = TokenResponse(
            accessToken: "access_abc123",
            refreshToken: "refresh_xyz789",
            expiresAt: 1735689600,
            athlete: TokenAthlete(id: 12345, firstName: "Test", lastName: "User")
        )

        let encoder = JSONEncoder()
        let decoder = JSONDecoder()

        let data = try encoder.encode(original)
        let decoded = try decoder.decode(TokenResponse.self, from: data)

        #expect(decoded.accessToken == original.accessToken)
        #expect(decoded.refreshToken == original.refreshToken)
        #expect(decoded.expiresAt == original.expiresAt)
        #expect(decoded.athlete?.id == original.athlete?.id)
    }

    // MARK: - RefreshTokenResponse Additional Tests

    @Test("RefreshTokenResponse encodes and decodes correctly")
    func refreshTokenResponseRoundTrip() throws {
        let original = RefreshTokenResponse(
            accessToken: "new_access",
            refreshToken: "new_refresh",
            expiresAt: 1735862400
        )

        let encoder = JSONEncoder()
        let decoder = JSONDecoder()

        let data = try encoder.encode(original)
        let decoded = try decoder.decode(RefreshTokenResponse.self, from: data)

        #expect(decoded.accessToken == original.accessToken)
        #expect(decoded.refreshToken == original.refreshToken)
        #expect(decoded.expiresAt == original.expiresAt)
    }

    // MARK: - Error Variations Tests

    @Test("StravaError rateLimited formats time correctly")
    func stravaErrorRateLimitedTimeFormat() {
        // Test with a specific time
        let resetTime = Date(timeIntervalSince1970: 1706180400)  // 2024-01-25 10:00:00
        let error = StravaError.rateLimited(resetTime: resetTime)
        let description = error.errorDescription ?? ""

        #expect(description.contains("Rate limited"))
        #expect(description.contains("after"))
    }

    @Test("StravaError serverError various codes")
    func stravaErrorServerErrorCodes() {
        let codes = [400, 401, 403, 404, 500, 502, 503, 504]

        for code in codes {
            let error = StravaError.serverError(statusCode: code)
            #expect(error.errorDescription?.contains("\(code)") == true)
        }
    }

    @Test("StravaError is Sendable")
    func stravaErrorSendable() async {
        let error = StravaError.authRequired

        let task = Task { @Sendable in
            return error.errorDescription
        }

        let description = await task.value
        #expect(description != nil)
    }
}

import Testing
import Foundation
@testable import ClubCalendar

@Suite("AuthService")
struct AuthServiceTests {
    // MARK: - AuthError Tests

    @Test("Auth error descriptions are meaningful")
    func authErrorDescriptions() {
        let errors: [AuthError] = [
            .noCredentials,
            .cancelled,
            .sessionError(URLError(.notConnectedToInternet)),
            .noCallbackURL,
            .noAuthCode,
            .stravaError("access_denied"),
            .failedToStart
        ]

        for error in errors {
            #expect(error.errorDescription != nil)
            #expect(!error.errorDescription!.isEmpty)
        }
    }

    @Test("Auth error descriptions contain relevant information")
    func authErrorDescriptionsContainRelevantInfo() {
        #expect(AuthError.noCredentials.errorDescription?.contains("credentials") == true)
        #expect(AuthError.cancelled.errorDescription?.contains("cancelled") == true)
        #expect(AuthError.noCallbackURL.errorDescription?.contains("callback") == true)
        #expect(AuthError.noAuthCode.errorDescription?.contains("code") == true)
        #expect(AuthError.failedToStart.errorDescription?.contains("start") == true)

        let stravaError = AuthError.stravaError("access_denied")
        #expect(stravaError.errorDescription?.contains("access_denied") == true)

        let sessionError = AuthError.sessionError(URLError(.timedOut))
        #expect(sessionError.errorDescription?.contains("error") == true)
    }

    // MARK: - StravaError Tests (additional coverage)

    @Test("Strava error descriptions are meaningful")
    func stravaErrorDescriptions() {
        let errors: [StravaError] = [
            .authRequired,
            .invalidCredentials,
            .rateLimited(resetTime: nil),
            .rateLimited(resetTime: Date()),
            .networkError(underlying: URLError(.notConnectedToInternet)),
            .invalidResponse,
            .serverError(statusCode: 500),
            .serverError(statusCode: 503),
            .decodingError(underlying: DecodingError.dataCorrupted(.init(codingPath: [], debugDescription: "test"))),
            .noRefreshToken
        ]

        for error in errors {
            #expect(error.errorDescription != nil)
            #expect(!error.errorDescription!.isEmpty)
        }
    }

    @Test("Strava error descriptions contain relevant information")
    func stravaErrorDescriptionsContainRelevantInfo() {
        #expect(StravaError.authRequired.errorDescription?.contains("Authentication") == true)
        #expect(StravaError.invalidCredentials.errorDescription?.contains("credentials") == true)
        #expect(StravaError.noRefreshToken.errorDescription?.contains("refresh") == true)
        #expect(StravaError.invalidResponse.errorDescription?.contains("response") == true)

        let serverError = StravaError.serverError(statusCode: 500)
        #expect(serverError.errorDescription?.contains("500") == true)

        let rateLimited = StravaError.rateLimited(resetTime: nil)
        #expect(rateLimited.errorDescription?.contains("Rate limited") == true)

        let rateLimitedWithTime = StravaError.rateLimited(resetTime: Date())
        #expect(rateLimitedWithTime.errorDescription?.contains("after") == true)
    }

    @Test("Strava error with various server error codes", arguments: [
        (400, "400"),
        (401, "401"),
        (403, "403"),
        (404, "404"),
        (500, "500"),
        (502, "502"),
        (503, "503")
    ])
    func stravaErrorWithVariousServerCodes(statusCode: Int, expectedString: String) {
        let error = StravaError.serverError(statusCode: statusCode)
        #expect(error.errorDescription?.contains(expectedString) == true)
    }

    @Test("Strava error network errors wrap underlying error")
    func stravaErrorNetworkErrorsWrapUnderlying() {
        let urlError = URLError(.notConnectedToInternet)
        let error = StravaError.networkError(underlying: urlError)
        #expect(error.errorDescription?.contains("Network") == true)
    }

    @Test("Strava error decoding errors wrap underlying error")
    func stravaErrorDecodingErrorsWrapUnderlying() {
        let decodingError = DecodingError.keyNotFound(
            Club.CodingKeys.id,
            .init(codingPath: [], debugDescription: "Key not found")
        )
        let error = StravaError.decodingError(underlying: decodingError)
        #expect(error.errorDescription?.contains("decode") == true)
    }

    // MARK: - KeychainError Tests (additional coverage)

    @Test("Keychain error descriptions are meaningful")
    func keychainErrorDescriptions() {
        let errors: [KeychainError] = [
            .itemNotFound,
            .duplicateItem,
            .unexpectedStatus(-25300),
            .unexpectedStatus(0),
            .dataConversionFailed
        ]

        for error in errors {
            #expect(error.errorDescription != nil)
            #expect(!error.errorDescription!.isEmpty)
        }
    }

    @Test("Keychain error descriptions contain relevant information")
    func keychainErrorDescriptionsContainRelevantInfo() {
        #expect(KeychainError.itemNotFound.errorDescription?.contains("not found") == true)
        #expect(KeychainError.duplicateItem.errorDescription?.contains("exists") == true)
        #expect(KeychainError.dataConversionFailed.errorDescription?.contains("convert") == true)

        let unexpectedError = KeychainError.unexpectedStatus(-25300)
        #expect(unexpectedError.errorDescription?.contains("-25300") == true)
    }
}

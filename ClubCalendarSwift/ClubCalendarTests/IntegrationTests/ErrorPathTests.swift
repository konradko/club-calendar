import Testing
import Foundation
@testable import ClubCalendar

@Suite("Error Path Coverage")
struct ErrorPathTests {
    // MARK: - StravaError Comprehensive Tests

    @Test("StravaError authRequired description")
    func stravaErrorAuthRequired() {
        let error = StravaError.authRequired
        #expect(error.errorDescription?.contains("Authentication") == true)
        #expect(error.errorDescription?.contains("Strava") == true)
    }

    @Test("StravaError invalidCredentials description")
    func stravaErrorInvalidCredentials() {
        let error = StravaError.invalidCredentials
        #expect(error.errorDescription?.contains("Invalid") == true)
        #expect(error.errorDescription?.contains("credentials") == true)
    }

    @Test("StravaError rateLimited with reset time")
    func stravaErrorRateLimitedWithTime() {
        let futureDate = Date().addingTimeInterval(3600)  // 1 hour from now
        let error = StravaError.rateLimited(resetTime: futureDate)
        #expect(error.errorDescription?.contains("Rate limited") == true)
        #expect(error.errorDescription?.contains("after") == true)
    }

    @Test("StravaError rateLimited without reset time")
    func stravaErrorRateLimitedWithoutTime() {
        let error = StravaError.rateLimited(resetTime: nil)
        #expect(error.errorDescription?.contains("Rate limited") == true)
        #expect(error.errorDescription?.contains("later") == true)
    }

    @Test("StravaError networkError wraps underlying")
    func stravaErrorNetworkError() {
        let underlying = URLError(.networkConnectionLost)
        let error = StravaError.networkError(underlying: underlying)
        #expect(error.errorDescription?.contains("Network") == true)
    }

    @Test("StravaError invalidResponse description")
    func stravaErrorInvalidResponse() {
        let error = StravaError.invalidResponse
        #expect(error.errorDescription?.contains("Invalid") == true)
        #expect(error.errorDescription?.contains("response") == true)
    }

    @Test("StravaError serverError with code")
    func stravaErrorServerError() {
        let error = StravaError.serverError(statusCode: 500)
        #expect(error.errorDescription?.contains("500") == true)
        #expect(error.errorDescription?.contains("Server") == true)
    }

    @Test("StravaError decodingError wraps underlying")
    func stravaErrorDecodingError() {
        let underlying = DecodingError.dataCorrupted(.init(codingPath: [], debugDescription: "test"))
        let error = StravaError.decodingError(underlying: underlying)
        #expect(error.errorDescription?.contains("decode") == true)
    }

    @Test("StravaError noRefreshToken description")
    func stravaErrorNoRefreshToken() {
        let error = StravaError.noRefreshToken
        #expect(error.errorDescription?.contains("refresh") == true)
        #expect(error.errorDescription?.contains("token") == true)
    }

    // MARK: - CalendarError Comprehensive Tests

    @Test("CalendarError accessDenied description")
    func calendarErrorAccessDenied() {
        let error = CalendarError.accessDenied
        #expect(error.errorDescription?.contains("denied") == true)
        #expect(error.errorDescription?.contains("Calendar") == true)
    }

    @Test("CalendarError accessRestricted description")
    func calendarErrorAccessRestricted() {
        let error = CalendarError.accessRestricted
        #expect(error.errorDescription?.contains("restricted") == true)
    }

    @Test("CalendarError calendarNotFound description")
    func calendarErrorCalendarNotFound() {
        let error = CalendarError.calendarNotFound
        #expect(error.errorDescription?.contains("calendar") == true)
    }

    @Test("CalendarError eventCreationFailed description")
    func calendarErrorEventCreationFailed() {
        let error = CalendarError.eventCreationFailed
        #expect(error.errorDescription?.contains("create") == true)
    }

    @Test("CalendarError eventUpdateFailed description")
    func calendarErrorEventUpdateFailed() {
        let error = CalendarError.eventUpdateFailed
        #expect(error.errorDescription?.contains("update") == true)
    }

    @Test("CalendarError unknownError wraps underlying")
    func calendarErrorUnknownError() {
        let underlying = NSError(domain: "TestDomain", code: 123, userInfo: [NSLocalizedDescriptionKey: "Custom error"])
        let error = CalendarError.unknownError(underlying)
        #expect(error.errorDescription?.contains("Custom error") == true)
    }

    // MARK: - AuthError Comprehensive Tests

    @Test("AuthError noCredentials description")
    func authErrorNoCredentials() {
        let error = AuthError.noCredentials
        #expect(error.errorDescription?.contains("credentials") == true)
    }

    @Test("AuthError cancelled description")
    func authErrorCancelled() {
        let error = AuthError.cancelled
        #expect(error.errorDescription?.contains("cancelled") == true)
    }

    @Test("AuthError sessionError wraps underlying")
    func authErrorSessionError() {
        let underlying = URLError(.timedOut)
        let error = AuthError.sessionError(underlying)
        #expect(error.errorDescription?.contains("error") == true)
    }

    @Test("AuthError noCallbackURL description")
    func authErrorNoCallbackURL() {
        let error = AuthError.noCallbackURL
        #expect(error.errorDescription?.contains("callback") == true)
    }

    @Test("AuthError noAuthCode description")
    func authErrorNoAuthCode() {
        let error = AuthError.noAuthCode
        #expect(error.errorDescription?.contains("code") == true)
    }

    @Test("AuthError stravaError with message")
    func authErrorStravaError() {
        let error = AuthError.stravaError("access_denied")
        #expect(error.errorDescription?.contains("access_denied") == true)
    }

    @Test("AuthError failedToStart description")
    func authErrorFailedToStart() {
        let error = AuthError.failedToStart
        #expect(error.errorDescription?.contains("start") == true)
    }

    // MARK: - KeychainError Comprehensive Tests

    @Test("KeychainError itemNotFound description")
    func keychainErrorItemNotFound() {
        let error = KeychainError.itemNotFound
        #expect(error.errorDescription?.contains("not found") == true)
    }

    @Test("KeychainError duplicateItem description")
    func keychainErrorDuplicateItem() {
        let error = KeychainError.duplicateItem
        #expect(error.errorDescription?.contains("exists") == true)
    }

    @Test("KeychainError unexpectedStatus with code")
    func keychainErrorUnexpectedStatus() {
        let error = KeychainError.unexpectedStatus(-25300)
        #expect(error.errorDescription?.contains("-25300") == true)
    }

    @Test("KeychainError dataConversionFailed description")
    func keychainErrorDataConversionFailed() {
        let error = KeychainError.dataConversionFailed
        #expect(error.errorDescription?.contains("convert") == true)
    }

    // MARK: - Decoding Error Scenarios

    @Test("Club decoding fails with missing required field")
    func clubDecodingFailsWithMissingField() {
        let json = """
        {
            "name": "Incomplete Club",
            "member_count": 50
        }
        """

        let data = json.data(using: .utf8)!
        #expect(throws: Error.self) {
            try JSONDecoder().decode(Club.self, from: data)
        }
    }

    @Test("ClubEvent decoding fails with invalid date format")
    func clubEventDecodingFailsWithInvalidDate() {
        let json = """
        {
            "id": 1,
            "title": "Test Event",
            "club_name": "Test Club",
            "start_datetime": "not-a-date"
        }
        """

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let data = json.data(using: .utf8)!
        #expect(throws: Error.self) {
            try decoder.decode(ClubEvent.self, from: data)
        }
    }

    @Test("TokenResponse decoding fails with missing required field")
    func tokenResponseDecodingFailsWithMissingField() {
        let json = """
        {
            "access_token": "token123"
        }
        """

        let data = json.data(using: .utf8)!
        #expect(throws: Error.self) {
            try JSONDecoder().decode(TokenResponse.self, from: data)
        }
    }

    @Test("RefreshTokenResponse decoding fails with missing required field")
    func refreshTokenResponseDecodingFailsWithMissingField() {
        let json = """
        {
            "access_token": "token123",
            "refresh_token": "refresh123"
        }
        """

        let data = json.data(using: .utf8)!
        #expect(throws: Error.self) {
            try JSONDecoder().decode(RefreshTokenResponse.self, from: data)
        }
    }

    @Test("SyncableClub decoding fails with invalid data")
    func syncableClubDecodingFailsWithInvalidData() {
        let json = """
        {
            "club": "not an object",
            "isEnabled": true
        }
        """

        let data = json.data(using: .utf8)!
        #expect(throws: Error.self) {
            try JSONDecoder().decode(SyncableClub.self, from: data)
        }
    }
}

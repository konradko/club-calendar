import Testing
import Foundation
@testable import ClubCalendarMac
@testable import ClubCalendarCore

@Suite("Error Coverage Tests")
struct ErrorCoverageTests {
    // MARK: - StravaError Comprehensive Tests

    @Test("StravaError authRequired full coverage")
    func stravaErrorAuthRequired() {
        let error = StravaError.authRequired

        #expect(error.errorDescription != nil)
        #expect(error.errorDescription!.contains("Authentication"))
        #expect(error.errorDescription!.contains("Strava"))
    }

    @Test("StravaError invalidCredentials full coverage")
    func stravaErrorInvalidCredentials() {
        let error = StravaError.invalidCredentials

        #expect(error.errorDescription != nil)
        #expect(error.errorDescription!.contains("Invalid"))
        #expect(error.errorDescription!.contains("credentials"))
    }

    @Test("StravaError rateLimited with reset time formats correctly")
    func stravaErrorRateLimitedWithResetTime() {
        // Test with various times
        let times = [
            Date(),
            Date().addingTimeInterval(3600),
            Date().addingTimeInterval(7200),
            Date(timeIntervalSince1970: 1706180400)
        ]

        for time in times {
            let error = StravaError.rateLimited(resetTime: time)
            let description = error.errorDescription ?? ""

            #expect(description.contains("Rate limited"))
            #expect(description.contains("after"))
        }
    }

    @Test("StravaError rateLimited without reset time")
    func stravaErrorRateLimitedWithoutResetTime() {
        let error = StravaError.rateLimited(resetTime: nil)
        let description = error.errorDescription ?? ""

        #expect(description.contains("Rate limited"))
        #expect(description.contains("later"))
        #expect(!description.contains("after"))
    }

    @Test("StravaError networkError with various underlying errors")
    func stravaErrorNetworkErrorVariations() {
        let underlyingErrors: [Error] = [
            URLError(.notConnectedToInternet),
            URLError(.timedOut),
            URLError(.networkConnectionLost),
            URLError(.cannotFindHost),
            URLError(.cannotConnectToHost),
            NSError(domain: "TestDomain", code: 123, userInfo: [NSLocalizedDescriptionKey: "Test error"])
        ]

        for underlyingError in underlyingErrors {
            let error = StravaError.networkError(underlying: underlyingError)
            let description = error.errorDescription ?? ""

            #expect(description.contains("Network error"))
        }
    }

    @Test("StravaError invalidResponse full coverage")
    func stravaErrorInvalidResponse() {
        let error = StravaError.invalidResponse

        #expect(error.errorDescription != nil)
        #expect(error.errorDescription!.contains("Invalid"))
        #expect(error.errorDescription!.contains("response"))
    }

    @Test("StravaError serverError with all common codes")
    func stravaErrorServerErrorAllCodes() {
        let codes = [400, 401, 403, 404, 405, 408, 429, 500, 501, 502, 503, 504]

        for code in codes {
            let error = StravaError.serverError(statusCode: code)
            let description = error.errorDescription ?? ""

            #expect(description.contains("Server error"))
            #expect(description.contains("\(code)"))
        }
    }

    @Test("StravaError decodingError with various types")
    func stravaErrorDecodingErrorVariations() {
        let decodingErrors: [Error] = [
            DecodingError.dataCorrupted(.init(codingPath: [], debugDescription: "Corrupted")),
            DecodingError.typeMismatch(String.self, .init(codingPath: [], debugDescription: "Type mismatch")),
            DecodingError.valueNotFound(Int.self, .init(codingPath: [], debugDescription: "Not found")),
            NSError(domain: "DecodingDomain", code: 1, userInfo: [NSLocalizedDescriptionKey: "Decoding failed"])
        ]

        for underlyingError in decodingErrors {
            let error = StravaError.decodingError(underlying: underlyingError)
            let description = error.errorDescription ?? ""

            #expect(description.contains("decode"))
        }
    }

    @Test("StravaError noRefreshToken full coverage")
    func stravaErrorNoRefreshToken() {
        let error = StravaError.noRefreshToken

        #expect(error.errorDescription != nil)
        #expect(error.errorDescription!.contains("refresh token"))
        #expect(error.errorDescription!.contains("Strava"))
    }

    // MARK: - CalendarError Comprehensive Tests

    @Test("CalendarError accessDenied full coverage")
    func calendarErrorAccessDenied() {
        let error = CalendarError.accessDenied

        #expect(error.errorDescription != nil)
        #expect(error.errorDescription!.contains("denied"))
        #expect(error.errorDescription!.contains("Calendar"))
    }

    @Test("CalendarError accessRestricted full coverage")
    func calendarErrorAccessRestricted() {
        let error = CalendarError.accessRestricted

        #expect(error.errorDescription != nil)
        #expect(error.errorDescription!.contains("restricted"))
    }

    @Test("CalendarError calendarNotFound full coverage")
    func calendarErrorCalendarNotFound() {
        let error = CalendarError.calendarNotFound

        #expect(error.errorDescription != nil)
        #expect(error.errorDescription!.contains("calendar"))
    }

    @Test("CalendarError eventCreationFailed full coverage")
    func calendarErrorEventCreationFailed() {
        let error = CalendarError.eventCreationFailed

        #expect(error.errorDescription != nil)
        #expect(error.errorDescription!.contains("create"))
        #expect(error.errorDescription!.contains("event"))
    }

    @Test("CalendarError eventUpdateFailed full coverage")
    func calendarErrorEventUpdateFailed() {
        let error = CalendarError.eventUpdateFailed

        #expect(error.errorDescription != nil)
        #expect(error.errorDescription!.contains("update"))
        #expect(error.errorDescription!.contains("event"))
    }

    @Test("CalendarError unknownError with various underlying errors")
    func calendarErrorUnknownErrorVariations() {
        let underlyingErrors: [Error] = [
            NSError(domain: "TestDomain", code: 1, userInfo: [NSLocalizedDescriptionKey: "Test error"]),
            NSError(domain: "CalendarDomain", code: 100, userInfo: [NSLocalizedDescriptionKey: "Calendar failed"]),
            URLError(.unknown)
        ]

        for underlyingError in underlyingErrors {
            let error = CalendarError.unknownError(underlyingError)
            let description = error.errorDescription ?? ""

            #expect(description.contains("Calendar error"))
        }
    }

    // MARK: - AuthError Comprehensive Tests

    @Test("AuthError noCredentials full coverage")
    func authErrorNoCredentials() {
        let error = AuthError.noCredentials

        #expect(error.errorDescription != nil)
        #expect(error.errorDescription!.contains("credentials"))
    }

    @Test("AuthError cancelled full coverage")
    func authErrorCancelled() {
        let error = AuthError.cancelled

        #expect(error.errorDescription != nil)
        #expect(error.errorDescription!.contains("cancelled"))
    }

    @Test("AuthError sessionError with various underlying errors")
    func authErrorSessionErrorVariations() {
        let underlyingErrors: [Error] = [
            NSError(domain: "ASWebAuthenticationSessionErrorDomain", code: 1, userInfo: [NSLocalizedDescriptionKey: "Session failed"]),
            URLError(.userCancelledAuthentication),
            NSError(domain: "TestDomain", code: 42, userInfo: nil)
        ]

        for underlyingError in underlyingErrors {
            let error = AuthError.sessionError(underlyingError)
            let description = error.errorDescription ?? ""

            #expect(description.contains("Authentication error"))
        }
    }

    @Test("AuthError noCallbackURL full coverage")
    func authErrorNoCallbackURL() {
        let error = AuthError.noCallbackURL

        #expect(error.errorDescription != nil)
        #expect(error.errorDescription!.contains("callback"))
    }

    @Test("AuthError noAuthCode full coverage")
    func authErrorNoAuthCode() {
        let error = AuthError.noAuthCode

        #expect(error.errorDescription != nil)
        #expect(error.errorDescription!.contains("authorization code"))
    }

    @Test("AuthError stravaError with various messages")
    func authErrorStravaErrorVariations() {
        let errorMessages = [
            "access_denied",
            "invalid_request",
            "unauthorized_client",
            "unsupported_response_type",
            "invalid_scope"
        ]

        for message in errorMessages {
            let error = AuthError.stravaError(message)
            let description = error.errorDescription ?? ""

            #expect(description.contains("Strava error"))
            #expect(description.contains(message))
        }
    }

    @Test("AuthError failedToStart full coverage")
    func authErrorFailedToStart() {
        let error = AuthError.failedToStart

        #expect(error.errorDescription != nil)
        #expect(error.errorDescription!.contains("Failed"))
        #expect(error.errorDescription!.contains("start"))
    }

    // MARK: - KeychainError Comprehensive Tests

    @Test("KeychainError itemNotFound full coverage")
    func keychainErrorItemNotFound() {
        let error = KeychainError.itemNotFound

        #expect(error.errorDescription != nil)
        #expect(error.errorDescription!.contains("not found"))
    }

    @Test("KeychainError duplicateItem full coverage")
    func keychainErrorDuplicateItem() {
        let error = KeychainError.duplicateItem

        #expect(error.errorDescription != nil)
        #expect(error.errorDescription!.contains("already exists"))
    }

    @Test("KeychainError unexpectedStatus with various codes")
    func keychainErrorUnexpectedStatusVariations() {
        let statusCodes: [OSStatus] = [
            errSecItemNotFound,
            errSecDuplicateItem,
            errSecAuthFailed,
            errSecInteractionNotAllowed,
            -25300,
            -25291,
            0
        ]

        for code in statusCodes {
            let error = KeychainError.unexpectedStatus(code)
            let description = error.errorDescription ?? ""

            #expect(description.contains("Keychain error"))
            #expect(description.contains("\(code)"))
        }
    }

    @Test("KeychainError dataConversionFailed full coverage")
    func keychainErrorDataConversionFailed() {
        let error = KeychainError.dataConversionFailed

        #expect(error.errorDescription != nil)
        #expect(error.errorDescription!.contains("convert"))
    }

    // MARK: - Error Sendable Conformance Tests

    @Test("All error types are Sendable")
    func allErrorTypesAreSendable() async {
        // StravaError
        let stravaTask = Task { @Sendable in
            let error = StravaError.authRequired
            return error.errorDescription
        }
        let stravaDesc = await stravaTask.value
        #expect(stravaDesc != nil)

        // CalendarError
        let calendarTask = Task { @Sendable in
            let error = CalendarError.accessDenied
            return error.errorDescription
        }
        let calendarDesc = await calendarTask.value
        #expect(calendarDesc != nil)

        // AuthError
        let authTask = Task { @Sendable in
            let error = AuthError.cancelled
            return error.errorDescription
        }
        let authDesc = await authTask.value
        #expect(authDesc != nil)

        // KeychainError
        let keychainTask = Task { @Sendable in
            let error = KeychainError.itemNotFound
            return error.errorDescription
        }
        let keychainDesc = await keychainTask.value
        #expect(keychainDesc != nil)
    }

    // MARK: - CalendarAccessStatus Tests

    @Test("CalendarAccessStatus all cases")
    func calendarAccessStatusAllCases() {
        let statuses: [CalendarAccessStatus] = [
            .authorized,
            .denied,
            .restricted,
            .notDetermined
        ]

        // All cases should be distinct
        let descriptions = statuses.map { String(describing: $0) }
        let uniqueDescriptions = Set(descriptions)
        #expect(uniqueDescriptions.count == statuses.count)
    }

    @Test("CalendarAccessStatus Sendable conformance")
    func calendarAccessStatusSendable() async {
        let statuses: [CalendarAccessStatus] = [.authorized, .denied, .restricted, .notDetermined]

        for status in statuses {
            let task = Task { @Sendable in
                return status
            }
            let result = await task.value
            #expect(String(describing: result) == String(describing: status))
        }
    }
}

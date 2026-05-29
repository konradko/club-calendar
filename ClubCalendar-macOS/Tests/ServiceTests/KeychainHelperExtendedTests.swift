import Testing
import Foundation
@testable import ClubCalendarMac
@testable import ClubCalendarCore

@Suite("KeychainHelper Extended Tests")
struct KeychainHelperExtendedTests {
    // MARK: - KeychainKey Tests

    @Test("KeychainKey raw values are unique")
    func keychainKeyRawValuesUnique() {
        let keys: [KeychainKey] = [
            .clientId,
            .clientSecret,
            .accessToken,
            .refreshToken,
            .tokenExpiry,
            .athleteId,
            .athleteName
        ]

        let rawValues = Set(keys.map(\.rawValue))
        #expect(rawValues.count == keys.count)
    }

    @Test("KeychainKey raw values have proper prefix")
    func keychainKeyRawValuesHavePrefix() {
        let keys: [KeychainKey] = [
            .clientId,
            .clientSecret,
            .accessToken,
            .refreshToken,
            .tokenExpiry,
            .athleteId,
            .athleteName
        ]

        for key in keys {
            #expect(key.rawValue.hasPrefix("com.clubcalendar."))
        }
    }

    @Test("KeychainKey is Sendable")
    func keychainKeyIsSendable() async {
        let key: KeychainKey = .clientId

        let task = Task { @Sendable in
            return key.rawValue
        }

        let rawValue = await task.value
        #expect(rawValue == "com.clubcalendar.clientId")
    }

    // MARK: - KeychainError Tests

    @Test("KeychainError itemNotFound description")
    func keychainErrorItemNotFoundDescription() {
        let error = KeychainError.itemNotFound
        #expect(error.errorDescription?.contains("not found") == true)
    }

    @Test("KeychainError duplicateItem description")
    func keychainErrorDuplicateItemDescription() {
        let error = KeychainError.duplicateItem
        #expect(error.errorDescription?.contains("already exists") == true)
    }

    @Test("KeychainError unexpectedStatus description")
    func keychainErrorUnexpectedStatusDescription() {
        let error = KeychainError.unexpectedStatus(-25300)
        #expect(error.errorDescription?.contains("-25300") == true)
    }

    @Test("KeychainError dataConversionFailed description")
    func keychainErrorDataConversionFailedDescription() {
        let error = KeychainError.dataConversionFailed
        #expect(error.errorDescription?.contains("convert") == true)
    }

    @Test("KeychainError is Sendable")
    func keychainErrorIsSendable() async {
        let error: KeychainError = .itemNotFound

        let task = Task { @Sendable in
            return error.errorDescription
        }

        let description = await task.value
        #expect(description != nil)
    }

    @Test("KeychainError with various OSStatus codes", arguments: [
        -25291, -25292, -25293, -25294, -25299, -25300
    ])
    func keychainErrorWithVariousOSStatusCodes(code: Int32) {
        let status = OSStatus(code)
        let error = KeychainError.unexpectedStatus(status)
        let description = error.errorDescription ?? ""

        #expect(description.contains("\(code)"))
    }

    // MARK: - MockKeychainHelper Tests

    @Test("MockKeychainHelper save and get string")
    func mockKeychainHelperSaveAndGetString() async throws {
        let mockKeychain = MockKeychainHelper()

        try await mockKeychain.save("test_value", for: .clientId)
        let value = try await mockKeychain.getString(for: .clientId)

        #expect(value == "test_value")
    }

    @Test("MockKeychainHelper getStringOrNil returns nil for missing key")
    func mockKeychainHelperGetStringOrNilReturnNil() async {
        let mockKeychain = MockKeychainHelper()

        let value = await mockKeychain.getStringOrNil(for: .clientId)

        #expect(value == nil)
    }

    @Test("MockKeychainHelper exists returns correct value")
    func mockKeychainHelperExists() async throws {
        let mockKeychain = MockKeychainHelper()

        #expect(await mockKeychain.exists(key: .clientId) == false)

        try await mockKeychain.save("test", for: .clientId)

        #expect(await mockKeychain.exists(key: .clientId) == true)
    }

    @Test("MockKeychainHelper delete removes item")
    func mockKeychainHelperDelete() async throws {
        let mockKeychain = MockKeychainHelper()

        try await mockKeychain.save("test", for: .clientId)
        #expect(await mockKeychain.exists(key: .clientId) == true)

        try await mockKeychain.delete(key: .clientId)
        #expect(await mockKeychain.exists(key: .clientId) == false)
    }

    @Test("MockKeychainHelper saveTokens saves all tokens")
    func mockKeychainHelperSaveTokens() async throws {
        let mockKeychain = MockKeychainHelper()

        let expiryDate = Date().addingTimeInterval(3600)
        try await mockKeychain.saveTokens(
            accessToken: "access_123",
            refreshToken: "refresh_456",
            expiresAt: expiryDate
        )

        #expect(await mockKeychain.getStringOrNil(for: .accessToken) == "access_123")
        #expect(await mockKeychain.getStringOrNil(for: .refreshToken) == "refresh_456")
        #expect(await mockKeychain.getStringOrNil(for: .tokenExpiry) != nil)
    }

    @Test("MockKeychainHelper getValidAccessToken returns token when valid")
    func mockKeychainHelperGetValidAccessToken() async throws {
        let mockKeychain = MockKeychainHelper()

        // Set token that expires in 1 hour (more than 5 minutes)
        let expiryDate = Date().addingTimeInterval(3600)
        try await mockKeychain.saveTokens(
            accessToken: "valid_token",
            refreshToken: "refresh",
            expiresAt: expiryDate
        )

        let token = await mockKeychain.getValidAccessToken()
        #expect(token == "valid_token")
    }

    @Test("MockKeychainHelper getValidAccessToken returns nil when expired")
    func mockKeychainHelperGetValidAccessTokenExpired() async throws {
        let mockKeychain = MockKeychainHelper()

        // Set token that expired 1 hour ago
        let expiryDate = Date().addingTimeInterval(-3600)
        try await mockKeychain.saveTokens(
            accessToken: "expired_token",
            refreshToken: "refresh",
            expiresAt: expiryDate
        )

        let token = await mockKeychain.getValidAccessToken()
        #expect(token == nil)
    }

    @Test("MockKeychainHelper getValidAccessToken returns nil when almost expired")
    func mockKeychainHelperGetValidAccessTokenAlmostExpired() async throws {
        let mockKeychain = MockKeychainHelper()

        // Set token that expires in 2 minutes (less than 5 minute buffer)
        let expiryDate = Date().addingTimeInterval(120)
        try await mockKeychain.saveTokens(
            accessToken: "almost_expired",
            refreshToken: "refresh",
            expiresAt: expiryDate
        )

        let token = await mockKeychain.getValidAccessToken()
        #expect(token == nil)
    }

    @Test("MockKeychainHelper getTokenExpiry returns correct date")
    func mockKeychainHelperGetTokenExpiry() async throws {
        let mockKeychain = MockKeychainHelper()

        let expiryDate = Date(timeIntervalSince1970: 1706180400)
        try await mockKeychain.saveTokens(
            accessToken: "token",
            refreshToken: "refresh",
            expiresAt: expiryDate
        )

        let returnedExpiry = await mockKeychain.getTokenExpiry()
        #expect(returnedExpiry != nil)
        #expect(abs(returnedExpiry!.timeIntervalSince1970 - expiryDate.timeIntervalSince1970) < 1)
    }

    @Test("MockKeychainHelper clearAuth removes auth keys")
    func mockKeychainHelperClearAuth() async throws {
        let mockKeychain = MockKeychainHelper()

        try await mockKeychain.saveTokens(
            accessToken: "token",
            refreshToken: "refresh",
            expiresAt: Date()
        )
        try await mockKeychain.save("12345", for: .athleteId)
        try await mockKeychain.save("Test User", for: .athleteName)

        try await mockKeychain.clearAuth()

        #expect(await mockKeychain.exists(key: .accessToken) == false)
        #expect(await mockKeychain.exists(key: .refreshToken) == false)
        #expect(await mockKeychain.exists(key: .tokenExpiry) == false)
        #expect(await mockKeychain.exists(key: .athleteId) == false)
        #expect(await mockKeychain.exists(key: .athleteName) == false)
    }

    @Test("MockKeychainHelper clearAll removes all keys")
    func mockKeychainHelperClearAll() async throws {
        let mockKeychain = MockKeychainHelper()

        try await mockKeychain.save("client_id", for: .clientId)
        try await mockKeychain.save("client_secret", for: .clientSecret)
        try await mockKeychain.saveTokens(
            accessToken: "token",
            refreshToken: "refresh",
            expiresAt: Date()
        )

        try await mockKeychain.clearAll()

        #expect(await mockKeychain.exists(key: .clientId) == false)
        #expect(await mockKeychain.exists(key: .clientSecret) == false)
        #expect(await mockKeychain.exists(key: .accessToken) == false)
    }

    @Test("MockKeychainHelper hasAPICredentials returns correct value")
    func mockKeychainHelperHasAPICredentials() async throws {
        let mockKeychain = MockKeychainHelper()

        #expect(await mockKeychain.hasAPICredentials() == false)

        try await mockKeychain.save("id", for: .clientId)
        #expect(await mockKeychain.hasAPICredentials() == false)

        try await mockKeychain.save("secret", for: .clientSecret)
        #expect(await mockKeychain.hasAPICredentials() == true)
    }

    @Test("MockKeychainHelper isAuthenticated returns correct value")
    func mockKeychainHelperIsAuthenticated() async throws {
        let mockKeychain = MockKeychainHelper()

        #expect(await mockKeychain.isAuthenticated() == false)

        try await mockKeychain.save("refresh_token", for: .refreshToken)
        #expect(await mockKeychain.isAuthenticated() == true)
    }

    @Test("MockKeychainHelper setCredentials helper")
    func mockKeychainHelperSetCredentials() async throws {
        let mockKeychain = MockKeychainHelper()

        try await mockKeychain.setCredentials(clientId: "test_id", clientSecret: "test_secret")

        #expect(await mockKeychain.getStringOrNil(for: .clientId) == "test_id")
        #expect(await mockKeychain.getStringOrNil(for: .clientSecret) == "test_secret")
        #expect(await mockKeychain.hasAPICredentials() == true)
    }

    @Test("MockKeychainHelper setAuthenticatedState helper")
    func mockKeychainHelperSetAuthenticatedState() async throws {
        let mockKeychain = MockKeychainHelper()

        try await mockKeychain.setAuthenticatedState(
            accessToken: "access",
            refreshToken: "refresh",
            expiresAt: Date().addingTimeInterval(3600),
            athleteId: 12345,
            athleteName: "Test User"
        )

        #expect(await mockKeychain.isAuthenticated() == true)
        #expect(await mockKeychain.getStringOrNil(for: .athleteId) == "12345")
        #expect(await mockKeychain.getStringOrNil(for: .athleteName) == "Test User")
    }

    @Test("MockKeychainHelper getString throws for missing key")
    func mockKeychainHelperGetStringThrowsForMissingKey() async {
        let mockKeychain = MockKeychainHelper()

        do {
            _ = try await mockKeychain.getString(for: .clientId)
            #expect(Bool(false), "Expected error to be thrown")
        } catch {
            #expect(error is KeychainError)
            if case .itemNotFound = error as? KeychainError {
                // Expected
            } else {
                #expect(Bool(false), "Expected itemNotFound error")
            }
        }
    }
}

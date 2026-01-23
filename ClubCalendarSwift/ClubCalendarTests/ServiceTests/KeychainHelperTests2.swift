import Testing
import Foundation
@testable import ClubCalendar

@Suite("KeychainHelper Protocol Conformance Tests")
struct KeychainHelperProtocolTests {
    // MARK: - Protocol Method Tests

    @Test("MockKeychainHelper conforms to KeychainHelperProtocol")
    func mockKeychainHelperConformsToProtocol() async throws {
        let mock: any KeychainHelperProtocol = MockKeychainHelper()

        // Test all protocol methods
        try await mock.save("test", for: .clientId)
        let value = try await mock.getString(for: .clientId)
        #expect(value == "test")

        let optionalValue = await mock.getStringOrNil(for: .clientId)
        #expect(optionalValue == "test")

        let exists = await mock.exists(key: .clientId)
        #expect(exists == true)

        try await mock.delete(key: .clientId)
        let existsAfterDelete = await mock.exists(key: .clientId)
        #expect(existsAfterDelete == false)
    }

    @Test("MockKeychainHelper data methods work correctly")
    func mockKeychainHelperDataMethods() async throws {
        let mock = MockKeychainHelper()
        let testData = "Hello, World!".data(using: .utf8)!

        try await mock.save(testData, for: .accessToken)
        let retrieved = try await mock.getData(for: .accessToken)

        #expect(retrieved == testData)
    }

    @Test("MockKeychainHelper token validation with near-expiry")
    func mockKeychainHelperNearExpiry() async throws {
        let mock = MockKeychainHelper()
        // Token that expires in 4 minutes (less than 5 minute buffer)
        let nearExpiry = Date().addingTimeInterval(240)

        try await mock.saveTokens(accessToken: "nearExpired", refreshToken: "refresh", expiresAt: nearExpiry)

        let token = await mock.getValidAccessToken()
        #expect(token == nil)  // Should be nil because it's within 5 minute buffer
    }

    @Test("MockKeychainHelper token validation with exactly 5 minutes")
    func mockKeychainHelperExactly5Minutes() async throws {
        let mock = MockKeychainHelper()
        // Token that expires in exactly 5 minutes (at the boundary)
        let exactExpiry = Date().addingTimeInterval(300)

        try await mock.saveTokens(accessToken: "boundary", refreshToken: "refresh", expiresAt: exactExpiry)

        let token = await mock.getValidAccessToken()
        // At exactly 300 seconds, the token should be considered expired
        // because the check is `expiryDate > Date().addingTimeInterval(300)`
        #expect(token == nil)
    }

    @Test("MockKeychainHelper token validation with 6 minutes")
    func mockKeychainHelperJustOver5Minutes() async throws {
        let mock = MockKeychainHelper()
        // Token that expires in 6 minutes (just over the buffer)
        let validExpiry = Date().addingTimeInterval(360)

        try await mock.saveTokens(accessToken: "valid", refreshToken: "refresh", expiresAt: validExpiry)

        let token = await mock.getValidAccessToken()
        #expect(token == "valid")
    }

    @Test("MockKeychainHelper clearAll removes everything")
    func mockKeychainHelperClearAll() async throws {
        let mock = MockKeychainHelper()

        try await mock.save("client", for: .clientId)
        try await mock.save("secret", for: .clientSecret)
        try await mock.saveTokens(accessToken: "access", refreshToken: "refresh", expiresAt: Date())

        try await mock.clearAll()

        #expect(await mock.getStringOrNil(for: .clientId) == nil)
        #expect(await mock.getStringOrNil(for: .clientSecret) == nil)
        #expect(await mock.getStringOrNil(for: .accessToken) == nil)
        #expect(await mock.getStringOrNil(for: .refreshToken) == nil)
        #expect(await mock.hasAPICredentials() == false)
        #expect(await mock.isAuthenticated() == false)
    }

    // MARK: - KeychainKey Tests

    @Test("KeychainKey has correct raw values")
    func keychainKeyRawValues() {
        #expect(KeychainKey.clientId.rawValue == "com.clubcalendar.clientId")
        #expect(KeychainKey.clientSecret.rawValue == "com.clubcalendar.clientSecret")
        #expect(KeychainKey.accessToken.rawValue == "com.clubcalendar.accessToken")
        #expect(KeychainKey.refreshToken.rawValue == "com.clubcalendar.refreshToken")
        #expect(KeychainKey.tokenExpiry.rawValue == "com.clubcalendar.tokenExpiry")
        #expect(KeychainKey.athleteId.rawValue == "com.clubcalendar.athleteId")
        #expect(KeychainKey.athleteName.rawValue == "com.clubcalendar.athleteName")
    }

    @Test("All KeychainKey cases are unique")
    func keychainKeyUniqueness() {
        let allKeys: [KeychainKey] = [
            .clientId, .clientSecret, .accessToken, .refreshToken,
            .tokenExpiry, .athleteId, .athleteName
        ]
        let rawValues = allKeys.map(\.rawValue)
        let uniqueValues = Set(rawValues)
        #expect(uniqueValues.count == allKeys.count)
    }

    // MARK: - KeychainError Tests

    @Test("KeychainError descriptions are informative")
    func keychainErrorDescriptions() {
        let errors: [KeychainError] = [
            .itemNotFound,
            .duplicateItem,
            .unexpectedStatus(errSecAuthFailed),
            .dataConversionFailed
        ]

        for error in errors {
            #expect(error.errorDescription != nil)
            #expect(!error.errorDescription!.isEmpty)
        }
    }

    @Test("KeychainError unexpectedStatus includes status code")
    func keychainErrorUnexpectedStatusIncludesCode() {
        let testCodes: [OSStatus] = [-25300, 0, 1, -1, 12345]

        for code in testCodes {
            let error = KeychainError.unexpectedStatus(code)
            #expect(error.errorDescription?.contains("\(code)") == true)
        }
    }

    // MARK: - MockKeychainHelper Helper Method Tests

    @Test("MockKeychainHelper setCredentials helper works")
    func mockKeychainHelperSetCredentials() async throws {
        let mock = MockKeychainHelper()

        try await mock.setCredentials(clientId: "test_id", clientSecret: "test_secret")

        #expect(await mock.getStringOrNil(for: .clientId) == "test_id")
        #expect(await mock.getStringOrNil(for: .clientSecret) == "test_secret")
        #expect(await mock.hasAPICredentials() == true)
    }

    @Test("MockKeychainHelper setAuthenticatedState helper works")
    func mockKeychainHelperSetAuthenticatedState() async throws {
        let mock = MockKeychainHelper()
        let expiry = Date().addingTimeInterval(3600)

        try await mock.setAuthenticatedState(
            accessToken: "access",
            refreshToken: "refresh",
            expiresAt: expiry,
            athleteId: 12345,
            athleteName: "Test User"
        )

        #expect(await mock.getStringOrNil(for: .accessToken) == "access")
        #expect(await mock.getStringOrNil(for: .refreshToken) == "refresh")
        #expect(await mock.getStringOrNil(for: .athleteId) == "12345")
        #expect(await mock.getStringOrNil(for: .athleteName) == "Test User")
        #expect(await mock.isAuthenticated() == true)
    }
}

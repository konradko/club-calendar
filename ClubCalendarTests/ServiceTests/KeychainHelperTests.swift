import Testing
@testable import ClubCalendar

@Suite("KeychainHelper")
struct KeychainHelperTests {
    @Test("Keychain keys are unique")
    func keychainKeysAreUnique() {
        let keys: [KeychainKey] = [
            .clientId,
            .clientSecret,
            .accessToken,
            .refreshToken,
            .tokenExpiry,
            .athleteId,
            .athleteName
        ]

        let rawValues = keys.map(\.rawValue)
        let uniqueValues = Set(rawValues)

        #expect(rawValues.count == uniqueValues.count, "All keychain keys should have unique raw values")
    }

    @Test("Keychain error descriptions are meaningful")
    func keychainErrorDescriptions() {
        let errors: [KeychainError] = [
            .itemNotFound,
            .duplicateItem,
            .unexpectedStatus(-25300),
            .dataConversionFailed
        ]

        for error in errors {
            #expect(error.errorDescription != nil)
            #expect(!error.errorDescription!.isEmpty)
        }
    }

    @Test("Keychain key raw values", arguments: [
        (KeychainKey.clientId, "com.clubcalendar.clientId"),
        (KeychainKey.clientSecret, "com.clubcalendar.clientSecret"),
        (KeychainKey.accessToken, "com.clubcalendar.accessToken"),
        (KeychainKey.refreshToken, "com.clubcalendar.refreshToken"),
        (KeychainKey.tokenExpiry, "com.clubcalendar.tokenExpiry"),
        (KeychainKey.athleteId, "com.clubcalendar.athleteId"),
        (KeychainKey.athleteName, "com.clubcalendar.athleteName")
    ])
    func keychainKeyRawValues(key: KeychainKey, expected: String) {
        #expect(key.rawValue == expected)
    }
}

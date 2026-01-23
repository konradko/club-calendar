import Foundation
import Security

/// Keys for keychain items.
enum KeychainKey: String, Sendable {
    case clientId = "com.clubcalendar.clientId"
    case clientSecret = "com.clubcalendar.clientSecret"
    case accessToken = "com.clubcalendar.accessToken"
    case refreshToken = "com.clubcalendar.refreshToken"
    case tokenExpiry = "com.clubcalendar.tokenExpiry"
    case athleteId = "com.clubcalendar.athleteId"
    case athleteName = "com.clubcalendar.athleteName"
}

/// Errors that can occur during keychain operations.
enum KeychainError: Error, LocalizedError, Sendable {
    case itemNotFound
    case duplicateItem
    case unexpectedStatus(OSStatus)
    case dataConversionFailed

    var errorDescription: String? {
        switch self {
        case .itemNotFound:
            return "Item not found in keychain"
        case .duplicateItem:
            return "Item already exists in keychain"
        case .unexpectedStatus(let status):
            return "Keychain error: \(status)"
        case .dataConversionFailed:
            return "Failed to convert data"
        }
    }
}

/// Helper for secure keychain storage.
actor KeychainHelper {
    static let shared = KeychainHelper()

    // MARK: - String Operations

    /// Saves a string value to the keychain.
    func save(_ value: String, for key: KeychainKey) throws {
        guard let data = value.data(using: .utf8) else {
            throw KeychainError.dataConversionFailed
        }
        try save(data, for: key)
    }

    /// Retrieves a string value from the keychain.
    func getString(for key: KeychainKey) throws -> String {
        let data = try getData(for: key)
        guard let string = String(data: data, encoding: .utf8) else {
            throw KeychainError.dataConversionFailed
        }
        return string
    }

    /// Retrieves a string value from the keychain, returning nil if not found.
    func getStringOrNil(for key: KeychainKey) -> String? {
        try? getString(for: key)
    }

    // MARK: - Data Operations

    /// Saves data to the keychain.
    func save(_ data: Data, for key: KeychainKey) throws {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key.rawValue,
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock
        ]

        // Try to delete existing item first
        SecItemDelete(query as CFDictionary)

        let status = SecItemAdd(query as CFDictionary, nil)
        guard status == errSecSuccess else {
            throw KeychainError.unexpectedStatus(status)
        }
    }

    /// Retrieves data from the keychain.
    func getData(for key: KeychainKey) throws -> Data {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key.rawValue,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]

        var result: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        guard status == errSecSuccess else {
            if status == errSecItemNotFound {
                throw KeychainError.itemNotFound
            }
            throw KeychainError.unexpectedStatus(status)
        }

        guard let data = result as? Data else {
            throw KeychainError.dataConversionFailed
        }

        return data
    }

    /// Deletes an item from the keychain.
    func delete(key: KeychainKey) throws {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key.rawValue
        ]

        let status = SecItemDelete(query as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw KeychainError.unexpectedStatus(status)
        }
    }

    /// Checks if a key exists in the keychain.
    func exists(key: KeychainKey) -> Bool {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key.rawValue,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]

        let status = SecItemCopyMatching(query as CFDictionary, nil)
        return status == errSecSuccess
    }

    // MARK: - Token Management

    /// Saves OAuth tokens to the keychain.
    func saveTokens(accessToken: String, refreshToken: String, expiresAt: Date) throws {
        try save(accessToken, for: .accessToken)
        try save(refreshToken, for: .refreshToken)
        try save(String(expiresAt.timeIntervalSince1970), for: .tokenExpiry)
    }

    /// Retrieves the current access token if valid, nil otherwise.
    func getValidAccessToken() -> String? {
        guard let token = getStringOrNil(for: .accessToken),
              let expiryString = getStringOrNil(for: .tokenExpiry),
              let expiryTimestamp = Double(expiryString) else {
            return nil
        }

        let expiryDate = Date(timeIntervalSince1970: expiryTimestamp)
        // Consider token expired if less than 5 minutes remaining
        guard expiryDate > Date().addingTimeInterval(300) else {
            return nil
        }

        return token
    }

    /// Gets the token expiry date.
    func getTokenExpiry() -> Date? {
        guard let expiryString = getStringOrNil(for: .tokenExpiry),
              let expiryTimestamp = Double(expiryString) else {
            return nil
        }
        return Date(timeIntervalSince1970: expiryTimestamp)
    }

    /// Clears all auth-related keychain items.
    func clearAuth() throws {
        try delete(key: .accessToken)
        try delete(key: .refreshToken)
        try delete(key: .tokenExpiry)
        try delete(key: .athleteId)
        try delete(key: .athleteName)
    }

    /// Clears all keychain items including API credentials.
    func clearAll() throws {
        try clearAuth()
        try delete(key: .clientId)
        try delete(key: .clientSecret)
    }

    /// Checks if Strava API credentials are configured.
    func hasAPICredentials() -> Bool {
        exists(key: .clientId) && exists(key: .clientSecret)
    }

    /// Checks if user is authenticated (has refresh token).
    func isAuthenticated() -> Bool {
        exists(key: .refreshToken)
    }
}

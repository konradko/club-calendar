import Foundation
@testable import ClubCalendar

/// Mock keychain helper for testing services without actual keychain access.
actor MockKeychainHelper: KeychainHelperProtocol {
    private var storage: [String: String] = [:]
    private var dataStorage: [String: Data] = [:]

    func save(_ value: String, for key: KeychainKey) throws {
        storage[key.rawValue] = value
    }

    func getString(for key: KeychainKey) throws -> String {
        guard let value = storage[key.rawValue] else {
            throw KeychainError.itemNotFound
        }
        return value
    }

    func getStringOrNil(for key: KeychainKey) -> String? {
        storage[key.rawValue]
    }

    func save(_ data: Data, for key: KeychainKey) throws {
        dataStorage[key.rawValue] = data
    }

    func getData(for key: KeychainKey) throws -> Data {
        guard let data = dataStorage[key.rawValue] else {
            throw KeychainError.itemNotFound
        }
        return data
    }

    func delete(key: KeychainKey) throws {
        storage.removeValue(forKey: key.rawValue)
        dataStorage.removeValue(forKey: key.rawValue)
    }

    func exists(key: KeychainKey) -> Bool {
        storage[key.rawValue] != nil
    }

    func saveTokens(accessToken: String, refreshToken: String, expiresAt: Date) throws {
        try save(accessToken, for: .accessToken)
        try save(refreshToken, for: .refreshToken)
        try save(String(expiresAt.timeIntervalSince1970), for: .tokenExpiry)
    }

    func getValidAccessToken() -> String? {
        guard let token = getStringOrNil(for: .accessToken),
              let expiryString = getStringOrNil(for: .tokenExpiry),
              let expiryTimestamp = Double(expiryString) else {
            return nil
        }

        let expiryDate = Date(timeIntervalSince1970: expiryTimestamp)
        guard expiryDate > Date().addingTimeInterval(300) else {
            return nil
        }

        return token
    }

    func getTokenExpiry() -> Date? {
        guard let expiryString = getStringOrNil(for: .tokenExpiry),
              let expiryTimestamp = Double(expiryString) else {
            return nil
        }
        return Date(timeIntervalSince1970: expiryTimestamp)
    }

    func clearAuth() throws {
        try delete(key: .accessToken)
        try delete(key: .refreshToken)
        try delete(key: .tokenExpiry)
        try delete(key: .athleteId)
        try delete(key: .athleteName)
    }

    func clearAll() throws {
        storage.removeAll()
    }

    func hasAPICredentials() -> Bool {
        exists(key: .clientId) && exists(key: .clientSecret)
    }

    func isAuthenticated() -> Bool {
        exists(key: .refreshToken)
    }

    // Test helpers
    func setCredentials(clientId: String, clientSecret: String) throws {
        try save(clientId, for: .clientId)
        try save(clientSecret, for: .clientSecret)
    }

    func setAuthenticatedState(
        accessToken: String,
        refreshToken: String,
        expiresAt: Date,
        athleteId: Int? = nil,
        athleteName: String? = nil
    ) throws {
        try saveTokens(accessToken: accessToken, refreshToken: refreshToken, expiresAt: expiresAt)
        if let athleteId = athleteId {
            try save(String(athleteId), for: .athleteId)
        }
        if let athleteName = athleteName {
            try save(athleteName, for: .athleteName)
        }
    }
}

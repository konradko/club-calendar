import Foundation
import ClubCalendarCore

/// In-memory keychain stand-in for iOS tests. The iOS Simulator's real
/// keychain isn't reliably available to unsigned test bundles, so tests
/// inject this mock via the AppState DI initializer.
///
/// Mirrors the macOS test mock — keep the two in sync if either grows
/// new helper methods.
final class MockKeychainHelper: KeychainHelperProtocol, @unchecked Sendable {
    private let lock = NSLock()
    private var storage: [String: String] = [:]
    private var dataStorage: [String: Data] = [:]

    func save(_ value: String, for key: KeychainKey) throws {
        lock.withLock { storage[key.rawValue] = value }
    }

    func getString(for key: KeychainKey) throws -> String {
        try lock.withLock {
            guard let value = storage[key.rawValue] else {
                throw KeychainError.itemNotFound
            }
            return value
        }
    }

    func getStringOrNil(for key: KeychainKey) -> String? {
        lock.withLock { storage[key.rawValue] }
    }

    func save(_ data: Data, for key: KeychainKey) throws {
        lock.withLock { dataStorage[key.rawValue] = data }
    }

    func getData(for key: KeychainKey) throws -> Data {
        try lock.withLock {
            guard let data = dataStorage[key.rawValue] else {
                throw KeychainError.itemNotFound
            }
            return data
        }
    }

    func delete(key: KeychainKey) throws {
        lock.withLock {
            storage.removeValue(forKey: key.rawValue)
            dataStorage.removeValue(forKey: key.rawValue)
        }
    }

    func exists(key: KeychainKey) -> Bool {
        lock.withLock { storage[key.rawValue] != nil }
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
        lock.withLock {
            storage.removeAll()
            dataStorage.removeAll()
        }
    }

    func hasAPICredentials() -> Bool {
        exists(key: .clientId) && exists(key: .clientSecret)
    }

    func isAuthenticated() -> Bool {
        exists(key: .refreshToken)
    }
}

import Foundation

// MARK: - Keychain Protocol

/// Protocol for keychain operations, enabling testability.
/// The concrete `KeychainHelper` hits the system keychain; tests can substitute
/// `MockKeychainHelper` (see `ClubCalendarTests/ServiceTests/MockKeychainHelper.swift`).
public protocol KeychainHelperProtocol: Sendable {
    func save(_ value: String, for key: KeychainKey) throws
    func getString(for key: KeychainKey) throws -> String
    func getStringOrNil(for key: KeychainKey) -> String?
    func save(_ data: Data, for key: KeychainKey) throws
    func getData(for key: KeychainKey) throws -> Data
    func delete(key: KeychainKey) throws
    func exists(key: KeychainKey) -> Bool
    func saveTokens(accessToken: String, refreshToken: String, expiresAt: Date) throws
    func getValidAccessToken() -> String?
    func getTokenExpiry() -> Date?
    func clearAuth() throws
    func clearAll() throws
    func hasAPICredentials() -> Bool
    func isAuthenticated() -> Bool
}

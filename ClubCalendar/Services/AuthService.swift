import Foundation
import AppKit
import AuthenticationServices
import os

/// Handles OAuth authentication with Strava via ASWebAuthenticationSession.
@MainActor
final class AuthService: NSObject {
    private let keychain: KeychainHelper
    private let stravaService: StravaService
    private let callbackScheme = "clubcalendar"
    private var session: ASWebAuthenticationSession?

    init(keychain: KeychainHelper = .shared, stravaService: StravaService) {
        self.keychain = keychain
        self.stravaService = stravaService
        super.init()
    }

    /// The OAuth authorization URL for Strava.
    private func authorizationURL() -> URL? {
        guard let clientId = keychain.getStringOrNil(for: .clientId) else {
            return nil
        }

        var components = URLComponents(string: "https://www.strava.com/oauth/authorize")!
        components.queryItems = [
            URLQueryItem(name: "client_id", value: clientId),
            URLQueryItem(name: "redirect_uri", value: "\(callbackScheme)://callback"),
            URLQueryItem(name: "response_type", value: "code"),
            URLQueryItem(name: "scope", value: "read,activity:read,read_all"),
            URLQueryItem(name: "approval_prompt", value: "auto")
        ]
        return components.url
    }

    /// Starts the OAuth flow using ASWebAuthenticationSession.
    func authenticate() async throws {
        Logger.auth.info("Starting OAuth authentication flow")

        guard let url = authorizationURL() else {
            Logger.auth.error("No API credentials configured")
            throw AuthError.noCredentials
        }

        let callbackURL = try await startWebAuthSession(authURL: url)

        guard let components = URLComponents(url: callbackURL, resolvingAgainstBaseURL: false) else {
            throw AuthError.noCallbackURL
        }

        if let stravaError = components.queryItems?.first(where: { $0.name == "error" })?.value {
            throw AuthError.stravaError(stravaError)
        }

        guard let code = components.queryItems?.first(where: { $0.name == "code" })?.value else {
            throw AuthError.noAuthCode
        }

        Logger.auth.info("Received authorization code, exchanging for tokens")
        _ = try await stravaService.exchangeToken(code: code)
        Logger.auth.info("Authentication complete")
    }

    private func startWebAuthSession(authURL: URL) async throws -> URL {
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<URL, Error>) in
            let session = ASWebAuthenticationSession(
                url: authURL,
                callbackURLScheme: callbackScheme
            ) { callbackURL, error in
                if let error = error as? ASWebAuthenticationSessionError, error.code == .canceledLogin {
                    continuation.resume(throwing: AuthError.cancelled)
                    return
                }
                if let error = error {
                    continuation.resume(throwing: AuthError.sessionError(error))
                    return
                }
                guard let callbackURL = callbackURL else {
                    continuation.resume(throwing: AuthError.noCallbackURL)
                    return
                }
                continuation.resume(returning: callbackURL)
            }

            session.presentationContextProvider = self
            session.prefersEphemeralWebBrowserSession = false

            self.session = session

            if !session.start() {
                continuation.resume(throwing: AuthError.failedToStart)
            }
        }
    }

    /// Disconnects from Strava by clearing auth tokens.
    func disconnect() async throws {
        try keychain.clearAuth()
    }

    /// Checks if user is authenticated.
    func isAuthenticated() async -> Bool {
        keychain.isAuthenticated()
    }

    /// Gets the authenticated athlete's name.
    func getAthleteName() async -> String? {
        keychain.getStringOrNil(for: .athleteName)
    }
}

// MARK: - ASWebAuthenticationPresentationContextProviding

extension AuthService: ASWebAuthenticationPresentationContextProviding {
    nonisolated func presentationAnchor(
        for session: ASWebAuthenticationSession
    ) -> ASPresentationAnchor {
        // ASWebAuthenticationSession wants a window to attach to. On a menu-
        // bar app (LSUIElement) there is often no key window, so fall back
        // to the first window or a fresh anchor — the system handles the rest.
        MainActor.assumeIsolated {
            NSApplication.shared.keyWindow ?? NSApplication.shared.windows.first ?? ASPresentationAnchor()
        }
    }
}

// MARK: - Errors

enum AuthError: Error, LocalizedError, Sendable {
    case noCredentials
    case cancelled
    case sessionError(Error)
    case noCallbackURL
    case noAuthCode
    case stravaError(String)
    case failedToStart

    var errorDescription: String? {
        switch self {
        case .noCredentials:
            return "No Strava API credentials configured."
        case .cancelled:
            return "Authentication was cancelled."
        case .sessionError(let error):
            return "Authentication error: \(error.localizedDescription)"
        case .noCallbackURL:
            return "No callback URL received."
        case .noAuthCode:
            return "No authorization code in callback."
        case .stravaError(let error):
            return "Strava error: \(error)"
        case .failedToStart:
            return "Failed to start authentication session."
        }
    }
}

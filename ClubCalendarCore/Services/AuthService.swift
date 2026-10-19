import Foundation
import AuthenticationServices
import os
#if canImport(AppKit)
import AppKit
#endif
#if canImport(UIKit)
import UIKit
#endif

/// Handles OAuth authentication with Strava via ASWebAuthenticationSession.
///
/// Keychain-only members are `nonisolated @concurrent`: on macOS a keychain
/// read can block inside a SecurityAgent ACL prompt (shown once per item
/// after a signing-cert rotation), and blocking the main actor while the
/// menu-bar menu is tracking freezes keyboard input system-wide.
@MainActor
public final class AuthService: NSObject {
    private let keychain: any KeychainHelperProtocol
    private let stravaService: StravaService
    private let callbackScheme = "clubcalendar"
    private var session: ASWebAuthenticationSession?

    public init(
        keychain: any KeychainHelperProtocol = KeychainHelper.shared,
        stravaService: StravaService
    ) {
        self.keychain = keychain
        self.stravaService = stravaService
        super.init()
    }

    /// The OAuth authorization URL for Strava.
    @concurrent
    private nonisolated func authorizationURL() async -> URL? {
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
    public func authenticate() async throws {
        Logger.auth.info("Starting OAuth authentication flow")

        guard let url = await authorizationURL() else {
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
    @concurrent
    public nonisolated func disconnect() async throws {
        try keychain.clearAuth()
    }

    /// Checks if user is authenticated.
    @concurrent
    public nonisolated func isAuthenticated() async -> Bool {
        keychain.isAuthenticated()
    }

    /// Gets the authenticated athlete's name.
    @concurrent
    public nonisolated func getAthleteName() async -> String? {
        keychain.getStringOrNil(for: .athleteName)
    }
}

// MARK: - ASWebAuthenticationPresentationContextProviding

extension AuthService: ASWebAuthenticationPresentationContextProviding {
    public nonisolated func presentationAnchor(
        for session: ASWebAuthenticationSession
    ) -> ASPresentationAnchor {
        // ASWebAuthenticationSession wants a window to attach to. On macOS
        // (especially LSUIElement menu-bar apps) the key window may be
        // missing; on iOS we look up the first foreground window scene.
        MainActor.assumeIsolated {
            #if canImport(AppKit)
            return NSApplication.shared.keyWindow ?? NSApplication.shared.windows.first ?? ASPresentationAnchor()
            #elseif canImport(UIKit)
            let scenes = UIApplication.shared.connectedScenes
            guard let scene = (scenes.first { $0.activationState == .foregroundActive } as? UIWindowScene)
                ?? scenes.first as? UIWindowScene else {
                // OAuth without an active UIWindowScene is unreachable — the
                // user can't tap "Connect" without a foreground scene.
                fatalError("ASWebAuthenticationSession: no UIWindowScene available")
            }
            return scene.keyWindow ?? scene.windows.first ?? UIWindow(windowScene: scene)
            #else
            return ASPresentationAnchor()
            #endif
        }
    }
}

// MARK: - Errors

public enum AuthError: Error, LocalizedError, Sendable {
    case noCredentials
    case cancelled
    case sessionError(Error)
    case noCallbackURL
    case noAuthCode
    case stravaError(String)
    case failedToStart

    public var errorDescription: String? {
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

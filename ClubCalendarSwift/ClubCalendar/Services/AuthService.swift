import Foundation
import AppKit
import Network

/// Handles OAuth authentication with Strava using localhost callback.
@MainActor
final class AuthService {
    private let keychain: KeychainHelper
    private let stravaService: StravaService
    private let callbackPort: UInt16 = 51678
    private var listener: NWListener?
    private var authContinuation: CheckedContinuation<String, Error>?

    init(keychain: KeychainHelper = .shared, stravaService: StravaService) {
        self.keychain = keychain
        self.stravaService = stravaService
    }

    /// The OAuth authorization URL for Strava.
    private func authorizationURL() async -> URL? {
        guard let clientId = await keychain.getStringOrNil(for: .clientId) else {
            return nil
        }

        var components = URLComponents(string: "https://www.strava.com/oauth/authorize")!
        components.queryItems = [
            URLQueryItem(name: "client_id", value: clientId),
            URLQueryItem(name: "redirect_uri", value: "http://localhost:\(callbackPort)/callback"),
            URLQueryItem(name: "response_type", value: "code"),
            URLQueryItem(name: "scope", value: "read,activity:read,read_all"),
            URLQueryItem(name: "approval_prompt", value: "auto")
        ]
        return components.url
    }

    /// Starts the OAuth flow by opening browser and listening for callback.
    func authenticate() async throws {
        guard let url = await authorizationURL() else {
            throw AuthError.noCredentials
        }

        // Get the auth code via localhost callback
        let code = try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<String, Error>) in
            self.authContinuation = continuation

            // Start local server to receive callback
            do {
                try startCallbackServer()
            } catch {
                continuation.resume(throwing: AuthError.failedToStart)
                return
            }

            // Open browser for authentication
            NSWorkspace.shared.open(url)
        }

        // Exchange code for tokens
        _ = try await stravaService.exchangeToken(code: code)
    }

    /// Starts a local HTTP server to receive the OAuth callback.
    private func startCallbackServer() throws {
        let parameters = NWParameters.tcp
        parameters.allowLocalEndpointReuse = true

        listener = try NWListener(using: parameters, on: NWEndpoint.Port(rawValue: callbackPort)!)

        listener?.stateUpdateHandler = { [weak self] state in
            switch state {
            case .failed(let error):
                print("Listener failed: \(error)")
                Task { @MainActor in
                    self?.authContinuation?.resume(throwing: AuthError.failedToStart)
                    self?.authContinuation = nil
                }
            default:
                break
            }
        }

        listener?.newConnectionHandler = { [weak self] connection in
            self?.handleConnection(connection)
        }

        listener?.start(queue: .main)
    }

    /// Handles an incoming connection from the OAuth callback.
    private nonisolated func handleConnection(_ connection: NWConnection) {
        connection.start(queue: .main)

        connection.receive(minimumIncompleteLength: 1, maximumLength: 65536) { [weak self] data, _, _, error in
            guard let self = self else { return }

            if let data = data, let request = String(data: data, encoding: .utf8) {
                Task { @MainActor in
                    self.processCallback(request: request, connection: connection)
                }
            } else if let error = error {
                print("Connection error: \(error)")
                Task { @MainActor in
                    self.sendResponse(connection: connection, success: false, message: "Connection error")
                }
            }
        }
    }

    /// Processes the OAuth callback request and extracts the auth code.
    private func processCallback(request: String, connection: NWConnection) {
        // Parse the HTTP request to extract the path
        guard let firstLine = request.components(separatedBy: "\r\n").first,
              let urlPart = firstLine.components(separatedBy: " ").dropFirst().first,
              let urlComponents = URLComponents(string: "http://localhost\(urlPart)") else {
            sendResponse(connection: connection, success: false, message: "Invalid request")
            return
        }

        // Check for error in callback
        if let error = urlComponents.queryItems?.first(where: { $0.name == "error" })?.value {
            sendResponse(connection: connection, success: false, message: "Strava error: \(error)")
            stopCallbackServer()
            authContinuation?.resume(throwing: AuthError.stravaError(error))
            authContinuation = nil
            return
        }

        // Extract the authorization code
        guard let code = urlComponents.queryItems?.first(where: { $0.name == "code" })?.value else {
            sendResponse(connection: connection, success: false, message: "No authorization code received")
            stopCallbackServer()
            authContinuation?.resume(throwing: AuthError.noAuthCode)
            authContinuation = nil
            return
        }

        // Success - send response and complete
        sendResponse(connection: connection, success: true, message: "Authentication successful! You can close this window.")
        stopCallbackServer()
        authContinuation?.resume(returning: code)
        authContinuation = nil
    }

    /// Sends an HTTP response to the browser.
    private nonisolated func sendResponse(connection: NWConnection, success: Bool, message: String) {
        let html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Club Calendar - \(success ? "Success" : "Error")</title>
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: \(success ? "#f0fff0" : "#fff0f0"); }
                .container { text-align: center; padding: 40px; }
                h1 { color: \(success ? "#228B22" : "#DC143C"); }
                p { color: #666; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>\(success ? "✓" : "✗") \(success ? "Success" : "Error")</h1>
                <p>\(message)</p>
            </div>
        </body>
        </html>
        """

        let response = """
        HTTP/1.1 200 OK\r
        Content-Type: text/html; charset=utf-8\r
        Content-Length: \(html.utf8.count)\r
        Connection: close\r
        \r
        \(html)
        """

        connection.send(content: response.data(using: .utf8), completion: .contentProcessed { _ in
            connection.cancel()
        })
    }

    /// Stops the callback server.
    private func stopCallbackServer() {
        listener?.cancel()
        listener = nil
    }

    /// Disconnects from Strava by clearing auth tokens.
    func disconnect() async throws {
        try await keychain.clearAuth()
    }

    /// Checks if user is authenticated.
    func isAuthenticated() async -> Bool {
        await keychain.isAuthenticated()
    }

    /// Gets the authenticated athlete's name.
    func getAthleteName() async -> String? {
        await keychain.getStringOrNil(for: .athleteName)
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
            return "Failed to start authentication server."
        }
    }
}

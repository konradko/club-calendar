import Foundation
@testable import ClubCalendarMac
@testable import ClubCalendarCore

/// Mock URL session for testing network requests.
final class MockURLSession: URLSessionProtocol, @unchecked Sendable {
    private let lock = NSLock()
    var mockResponses: [URL: (Data, URLResponse)] = [:]
    var mockError: Error?
    var capturedRequests: [URLRequest] = []
    /// Delay applied before responding; lets tests keep requests in flight
    /// so concurrent callers actually overlap.
    var responseDelay: Duration?

    func data(for request: URLRequest) async throws -> (Data, URLResponse) {
        lock.withLock { capturedRequests.append(request) }

        if let delay = lock.withLock({ responseDelay }) {
            try await Task.sleep(for: delay)
        }

        if let error = lock.withLock({ mockError }) {
            throw error
        }

        guard let url = request.url,
              let response = lock.withLock({ mockResponses[url] }) else {
            throw URLError(.badURL)
        }

        return response
    }

    func setMockResponse(for url: URL, data: Data, statusCode: Int = 200) {
        let response = HTTPURLResponse(
            url: url,
            statusCode: statusCode,
            httpVersion: nil,
            headerFields: nil
        )!
        lock.withLock { mockResponses[url] = (data, response) }
    }

    func setMockJSONResponse(for url: URL, json: String, statusCode: Int = 200) {
        setMockResponse(for: url, data: json.data(using: .utf8)!, statusCode: statusCode)
    }
}

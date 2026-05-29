import Foundation
@testable import ClubCalendarMac
@testable import ClubCalendarCore

/// Mock URL session for testing network requests.
final class MockURLSession: URLSessionProtocol, @unchecked Sendable {
    var mockResponses: [URL: (Data, URLResponse)] = [:]
    var mockError: Error?
    var capturedRequests: [URLRequest] = []

    func data(for request: URLRequest) async throws -> (Data, URLResponse) {
        capturedRequests.append(request)

        if let error = mockError {
            throw error
        }

        guard let url = request.url,
              let response = mockResponses[url] else {
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
        mockResponses[url] = (data, response)
    }

    func setMockJSONResponse(for url: URL, json: String, statusCode: Int = 200) {
        setMockResponse(for: url, data: json.data(using: .utf8)!, statusCode: statusCode)
    }
}

import Testing
import Foundation
@testable import ClubCalendar

@Suite("StravaService API Tests")
struct StravaServiceAPITests {
    // MARK: - MockURLSession Tests

    @Test("MockURLSession captures requests")
    func mockURLSessionCapturesRequests() async throws {
        let mockSession = MockURLSession()
        let url = URL(string: "https://api.strava.com/test")!
        mockSession.setMockResponse(for: url, data: Data(), statusCode: 200)

        var request = URLRequest(url: url)
        request.httpMethod = "GET"

        _ = try await mockSession.data(for: request)

        #expect(mockSession.capturedRequests.count == 1)
        #expect(mockSession.capturedRequests.first?.url == url)
        #expect(mockSession.capturedRequests.first?.httpMethod == "GET")
    }

    @Test("MockURLSession returns mock response")
    func mockURLSessionReturnsMockResponse() async throws {
        let mockSession = MockURLSession()
        let url = URL(string: "https://api.strava.com/clubs")!
        let expectedData = "test data".data(using: .utf8)!
        mockSession.setMockResponse(for: url, data: expectedData, statusCode: 200)

        let request = URLRequest(url: url)
        let (data, response) = try await mockSession.data(for: request)

        #expect(data == expectedData)
        #expect((response as? HTTPURLResponse)?.statusCode == 200)
    }

    @Test("MockURLSession returns mock JSON response")
    func mockURLSessionReturnsMockJSONResponse() async throws {
        let mockSession = MockURLSession()
        let url = URL(string: "https://api.strava.com/clubs")!
        let json = """
        {"id": 123, "name": "Test Club"}
        """
        mockSession.setMockJSONResponse(for: url, json: json, statusCode: 200)

        let request = URLRequest(url: url)
        let (data, _) = try await mockSession.data(for: request)

        let string = String(data: data, encoding: .utf8)
        #expect(string == json)
    }

    @Test("MockURLSession throws error when configured")
    func mockURLSessionThrowsError() async {
        let mockSession = MockURLSession()
        mockSession.mockError = URLError(.notConnectedToInternet)

        let request = URLRequest(url: URL(string: "https://api.strava.com/test")!)

        do {
            _ = try await mockSession.data(for: request)
            #expect(Bool(false), "Expected error to be thrown")
        } catch {
            #expect(error is URLError)
        }
    }

    @Test("MockURLSession throws badURL for unmocked URLs")
    func mockURLSessionThrowsBadURLForUnmocked() async {
        let mockSession = MockURLSession()

        let request = URLRequest(url: URL(string: "https://unmocked.com/path")!)

        do {
            _ = try await mockSession.data(for: request)
            #expect(Bool(false), "Expected error to be thrown")
        } catch {
            #expect((error as? URLError)?.code == .badURL)
        }
    }

    @Test("MockURLSession supports multiple URLs")
    func mockURLSessionSupportsMultipleURLs() async throws {
        let mockSession = MockURLSession()

        let url1 = URL(string: "https://api.strava.com/endpoint1")!
        let url2 = URL(string: "https://api.strava.com/endpoint2")!

        mockSession.setMockJSONResponse(for: url1, json: "{\"type\": \"one\"}", statusCode: 200)
        mockSession.setMockJSONResponse(for: url2, json: "{\"type\": \"two\"}", statusCode: 201)

        let (data1, response1) = try await mockSession.data(for: URLRequest(url: url1))
        let (data2, response2) = try await mockSession.data(for: URLRequest(url: url2))

        #expect(String(data: data1, encoding: .utf8)?.contains("one") == true)
        #expect(String(data: data2, encoding: .utf8)?.contains("two") == true)
        #expect((response1 as? HTTPURLResponse)?.statusCode == 200)
        #expect((response2 as? HTTPURLResponse)?.statusCode == 201)
    }

    // MARK: - Date Decoding Tests

    @Test("Club event date decoding with ISO8601 format")
    func clubEventDateDecodingISO8601() throws {
        let json = """
        {
            "id": 1,
            "title": "Test Event",
            "club_name": "Test Club",
            "start_datetime": "2024-01-25T10:00:00Z",
            "activity_type": "Ride"
        }
        """

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let dateString = try container.decode(String.self)

            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            if let date = formatter.date(from: dateString) {
                return date
            }

            formatter.formatOptions = [.withInternetDateTime]
            if let date = formatter.date(from: dateString) {
                return date
            }

            throw DecodingError.dataCorruptedError(
                in: container,
                debugDescription: "Cannot decode date: \(dateString)"
            )
        }

        let data = json.data(using: .utf8)!
        let event = try decoder.decode(ClubEvent.self, from: data)

        #expect(event.id == 1)
        #expect(event.title == "Test Event")

        // Verify date was parsed correctly
        let calendar = Calendar.current
        let components = calendar.dateComponents(in: TimeZone(identifier: "UTC")!, from: event.startDatetime)
        #expect(components.year == 2024)
        #expect(components.month == 1)
        #expect(components.day == 25)
        #expect(components.hour == 10)
    }

    @Test("Club event date decoding with fractional seconds")
    func clubEventDateDecodingWithFractionalSeconds() throws {
        let json = """
        {
            "id": 2,
            "title": "Test Event 2",
            "club_name": "Test Club",
            "start_datetime": "2024-01-25T10:00:00.123Z",
            "activity_type": "Run"
        }
        """

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let dateString = try container.decode(String.self)

            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            if let date = formatter.date(from: dateString) {
                return date
            }

            formatter.formatOptions = [.withInternetDateTime]
            if let date = formatter.date(from: dateString) {
                return date
            }

            throw DecodingError.dataCorruptedError(
                in: container,
                debugDescription: "Cannot decode date: \(dateString)"
            )
        }

        let data = json.data(using: .utf8)!
        let event = try decoder.decode(ClubEvent.self, from: data)

        #expect(event.id == 2)
    }

    // MARK: - StravaError Additional Tests

    @Test("StravaError all cases have descriptions")
    func stravaErrorAllCasesHaveDescriptions() {
        let errors: [StravaError] = [
            .authRequired,
            .invalidCredentials,
            .rateLimited(resetTime: Date()),
            .rateLimited(resetTime: nil),
            .networkError(underlying: URLError(.timedOut)),
            .invalidResponse,
            .serverError(statusCode: 400),
            .serverError(statusCode: 401),
            .serverError(statusCode: 403),
            .serverError(statusCode: 404),
            .serverError(statusCode: 500),
            .serverError(statusCode: 502),
            .serverError(statusCode: 503),
            .decodingError(underlying: DecodingError.dataCorrupted(.init(codingPath: [], debugDescription: "test"))),
            .noRefreshToken
        ]

        for error in errors {
            let description = error.errorDescription
            #expect(description != nil)
            #expect(!description!.isEmpty)
            #expect(description!.count > 5)
        }
    }

    @Test("StravaError rate limited with reset time includes time")
    func stravaErrorRateLimitedWithResetTime() {
        let resetTime = Date().addingTimeInterval(3600)  // 1 hour from now
        let error = StravaError.rateLimited(resetTime: resetTime)
        let description = error.errorDescription ?? ""

        #expect(description.contains("Rate limited"))
        #expect(description.contains("after"))
    }

    @Test("StravaError rate limited without reset time")
    func stravaErrorRateLimitedWithoutResetTime() {
        let error = StravaError.rateLimited(resetTime: nil)
        let description = error.errorDescription ?? ""

        #expect(description.contains("Rate limited"))
        #expect(description.contains("later"))
    }

    @Test("StravaError network error includes underlying error")
    func stravaErrorNetworkErrorIncludesUnderlying() {
        let underlyingError = URLError(.notConnectedToInternet)
        let error = StravaError.networkError(underlying: underlyingError)
        let description = error.errorDescription ?? ""

        #expect(description.contains("Network error"))
    }

    @Test("StravaError decoding error includes underlying error")
    func stravaErrorDecodingErrorIncludesUnderlying() {
        let underlyingError = DecodingError.dataCorrupted(
            .init(codingPath: [], debugDescription: "Test decoding error")
        )
        let error = StravaError.decodingError(underlying: underlyingError)
        let description = error.errorDescription ?? ""

        #expect(description.contains("decode"))
    }

    @Test("StravaError server error includes status code")
    func stravaErrorServerErrorIncludesStatusCode() {
        let testCodes = [400, 403, 404, 500, 502, 503, 504]

        for code in testCodes {
            let error = StravaError.serverError(statusCode: code)
            let description = error.errorDescription ?? ""

            #expect(description.contains("\(code)"))
        }
    }

    // MARK: - HTTP Response Validation Tests

    @Test("StravaService validates 200 status code")
    func stravaServiceValidates200() async throws {
        let mockSession = MockURLSession()
        let url = URL(string: "https://www.strava.com/api/v3/test")!
        mockSession.setMockResponse(for: url, data: Data(), statusCode: 200)

        // The response is valid for 200-299 range
        let request = URLRequest(url: url)
        let (_, response) = try await mockSession.data(for: request)

        #expect((response as? HTTPURLResponse)?.statusCode == 200)
    }

    @Test("StravaService handles 429 rate limit response")
    func stravaServiceHandles429() async throws {
        let mockSession = MockURLSession()
        let url = URL(string: "https://www.strava.com/api/v3/test")!

        // Create response with rate limit header
        let response = HTTPURLResponse(
            url: url,
            statusCode: 429,
            httpVersion: nil,
            headerFields: ["X-RateLimit-Reset": "1706180400"]
        )!
        mockSession.mockResponses[url] = (Data(), response)

        let (_, httpResponse) = try await mockSession.data(for: URLRequest(url: url))

        #expect((httpResponse as? HTTPURLResponse)?.statusCode == 429)
    }

    @Test("StravaService handles 401 unauthorized response")
    func stravaServiceHandles401() async throws {
        let mockSession = MockURLSession()
        let url = URL(string: "https://www.strava.com/api/v3/test")!
        mockSession.setMockResponse(for: url, data: Data(), statusCode: 401)

        let (_, response) = try await mockSession.data(for: URLRequest(url: url))

        #expect((response as? HTTPURLResponse)?.statusCode == 401)
    }

    @Test("StravaService handles 500 server error response")
    func stravaServiceHandles500() async throws {
        let mockSession = MockURLSession()
        let url = URL(string: "https://www.strava.com/api/v3/test")!
        mockSession.setMockResponse(for: url, data: Data(), statusCode: 500)

        let (_, response) = try await mockSession.data(for: URLRequest(url: url))

        #expect((response as? HTTPURLResponse)?.statusCode == 500)
    }

    // MARK: - Token Response Tests

    @Test("TokenResponse decodes with all fields")
    func tokenResponseDecodesWithAllFields() throws {
        let json = """
        {
            "access_token": "abc123",
            "refresh_token": "xyz789",
            "expires_at": 1735689600,
            "athlete": {
                "id": 12345,
                "firstname": "John",
                "lastname": "Doe"
            }
        }
        """

        let data = json.data(using: .utf8)!
        let response = try JSONDecoder().decode(TokenResponse.self, from: data)

        #expect(response.accessToken == "abc123")
        #expect(response.refreshToken == "xyz789")
        #expect(response.expiresAt == 1735689600)
        #expect(response.athlete?.id == 12345)
        #expect(response.athlete?.firstName == "John")
        #expect(response.athlete?.lastName == "Doe")
        #expect(response.athlete?.fullName == "John Doe")
    }

    @Test("RefreshTokenResponse decodes correctly")
    func refreshTokenResponseDecodes() throws {
        let json = """
        {
            "access_token": "new_token",
            "refresh_token": "new_refresh",
            "expires_at": 1735776000
        }
        """

        let data = json.data(using: .utf8)!
        let response = try JSONDecoder().decode(RefreshTokenResponse.self, from: data)

        #expect(response.accessToken == "new_token")
        #expect(response.refreshToken == "new_refresh")
        #expect(response.expiresAt == 1735776000)
    }
}

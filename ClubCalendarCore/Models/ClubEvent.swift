import Foundation

/// Nested club object in Strava API response.
public struct EventClub: Codable, Sendable, Hashable {
    public let id: Int
    public let name: String

    public init(id: Int, name: String) {
        self.id = id
        self.name = name
    }

    enum CodingKeys: String, CodingKey {
        case id
        case name
    }
}

/// Represents a Strava club event.
///
/// The Strava API returns events with a nested `club` object and an
/// `upcoming_occurrences` array of ISO 8601 UTC timestamps. This model
/// handles both the real API format and a flat test format for convenience.
public struct ClubEvent: Identifiable, Sendable, Hashable {
    public let id: Int
    public let title: String
    public let clubId: Int
    public let clubName: String
    public let description: String?
    public let activityType: String?
    public let startDatetime: Date
    public let address: String?
    public let privateEvent: Bool?
    public let organizingAthlete: Athlete?
    public let routeId: Int?

    /// The emoji representing this event's activity type.
    public var activityEmoji: String {
        ActivityEmoji.emoji(for: activityType)
    }

    /// Formatted title with emoji prefix.
    public var formattedTitle: String {
        "\(activityEmoji) \(clubName): \(title)"
    }

    /// The Strava URL for this event.
    public var stravaURL: URL? {
        URL(string: "https://www.strava.com/clubs/\(clubId)/group_events/\(id)")
    }

    public init(
        id: Int,
        title: String,
        clubName: String,
        clubId: Int = 0,
        description: String?,
        activityType: String?,
        startDatetime: Date,
        address: String?,
        privateEvent: Bool?,
        organizingAthlete: Athlete?,
        routeId: Int?
    ) {
        self.id = id
        self.title = title
        self.clubId = clubId
        self.clubName = clubName
        self.description = description
        self.activityType = activityType
        self.startDatetime = startDatetime
        self.address = address
        self.privateEvent = privateEvent
        self.organizingAthlete = organizingAthlete
        self.routeId = routeId
    }
}

// MARK: - Codable

extension ClubEvent: Codable {
    enum CodingKeys: String, CodingKey {
        case id
        case title
        case description
        case activityType = "activity_type"
        case address
        case privateEvent = "private"
        case organizingAthlete = "organizing_athlete"
        case routeId = "route_id"
        // API response fields
        case club
        case upcomingOccurrences = "upcoming_occurrences"
        // Legacy flat fields (used in tests / re-encoding)
        case clubId = "club_id"
        case clubName = "club_name"
        case startDatetime = "start_datetime"
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)

        id = try container.decode(Int.self, forKey: .id)
        title = try container.decode(String.self, forKey: .title)
        description = try container.decodeIfPresent(String.self, forKey: .description)
        activityType = try container.decodeIfPresent(String.self, forKey: .activityType)
        address = try container.decodeIfPresent(String.self, forKey: .address)
        privateEvent = try container.decodeIfPresent(Bool.self, forKey: .privateEvent)
        organizingAthlete = try container.decodeIfPresent(Athlete.self, forKey: .organizingAthlete)
        routeId = try container.decodeIfPresent(Int.self, forKey: .routeId)

        // Club name + id: try nested club object first, then flat club_name/club_id
        if let club = try container.decodeIfPresent(EventClub.self, forKey: .club) {
            clubId = club.id
            clubName = club.name
        } else {
            clubId = try container.decodeIfPresent(Int.self, forKey: .clubId) ?? 0
            clubName = try container.decode(String.self, forKey: .clubName)
        }

        // Start datetime: try upcoming_occurrences[0] first, then flat start_datetime
        if let occurrences = try container.decodeIfPresent([String].self, forKey: .upcomingOccurrences),
           let first = occurrences.first {
            startDatetime = try Self.parseDate(first)
        } else {
            let dateString = try container.decode(String.self, forKey: .startDatetime)
            startDatetime = try Self.parseDate(dateString)
        }
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)

        try container.encode(id, forKey: .id)
        try container.encode(title, forKey: .title)
        try container.encodeIfPresent(description, forKey: .description)
        try container.encodeIfPresent(activityType, forKey: .activityType)
        try container.encodeIfPresent(address, forKey: .address)
        try container.encodeIfPresent(privateEvent, forKey: .privateEvent)
        try container.encodeIfPresent(organizingAthlete, forKey: .organizingAthlete)
        try container.encodeIfPresent(routeId, forKey: .routeId)
        try container.encode(clubId, forKey: .clubId)
        try container.encode(clubName, forKey: .clubName)

        try container.encode(startDatetime.formatted(.iso8601), forKey: .startDatetime)
    }

    /// Parses an ISO 8601 date string (with or without fractional seconds).
    private static func parseDate(_ string: String) throws -> Date {
        if let date = try? Date(string, strategy: .iso8601) { return date }
        if let date = try? Date(string, strategy: .iso8601.year().month().day().dateTimeSeparator(.standard).time(includingFractionalSeconds: true)) {
            return date
        }
        throw DecodingError.dataCorrupted(
            DecodingError.Context(
                codingPath: [],
                debugDescription: "Cannot decode date: \(string)"
            )
        )
    }
}

/// Minimal athlete information for event organizer.
public struct Athlete: Codable, Sendable, Hashable {
    public let id: Int
    public let firstName: String?
    public let lastName: String?

    public init(id: Int, firstName: String?, lastName: String?) {
        self.id = id
        self.firstName = firstName
        self.lastName = lastName
    }

    enum CodingKeys: String, CodingKey {
        case id
        case firstName = "firstname"
        case lastName = "lastname"
    }

    public var fullName: String {
        [firstName, lastName].compactMap { $0 }.joined(separator: " ")
    }
}

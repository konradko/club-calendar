import Foundation

/// Represents a Strava club event.
struct ClubEvent: Codable, Identifiable, Sendable, Hashable {
    let id: Int
    let title: String
    let clubName: String
    let description: String?
    let activityType: String?
    let startDatetime: Date
    let address: String?
    let privateEvent: Bool?
    let organizingAthlete: Athlete?
    let routeId: Int?

    enum CodingKeys: String, CodingKey {
        case id
        case title
        case clubName = "club_name"
        case description
        case activityType = "activity_type"
        case startDatetime = "start_datetime"
        case address
        case privateEvent = "private"
        case organizingAthlete = "organizing_athlete"
        case routeId = "route_id"
    }

    /// The emoji representing this event's activity type.
    var activityEmoji: String {
        ActivityEmoji.emoji(for: activityType)
    }

    /// Formatted title with emoji prefix.
    var formattedTitle: String {
        "\(activityEmoji) \(clubName): \(title)"
    }

    /// The Strava URL for this event.
    var stravaURL: URL? {
        URL(string: "https://www.strava.com/clubs/events/\(id)")
    }
}

/// Minimal athlete information for event organizer.
struct Athlete: Codable, Sendable, Hashable {
    let id: Int
    let firstName: String?
    let lastName: String?

    enum CodingKeys: String, CodingKey {
        case id
        case firstName = "firstname"
        case lastName = "lastname"
    }

    var fullName: String {
        [firstName, lastName].compactMap { $0 }.joined(separator: " ")
    }
}

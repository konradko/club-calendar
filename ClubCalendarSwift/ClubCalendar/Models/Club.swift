import Foundation

/// Represents a Strava club.
struct Club: Codable, Identifiable, Sendable, Hashable {
    let id: Int
    let name: String
    let memberCount: Int
    let city: String?
    let sportType: String?
    let profileMedium: String?

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case memberCount = "member_count"
        case city
        case sportType = "sport_type"
        case profileMedium = "profile_medium"
    }
}

/// A club with its sync-enabled state for settings persistence.
struct SyncableClub: Codable, Identifiable, Sendable, Hashable {
    let club: Club
    var isEnabled: Bool

    var id: Int { club.id }
}

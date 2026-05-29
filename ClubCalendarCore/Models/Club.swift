import Foundation

/// Represents a Strava club.
public struct Club: Codable, Identifiable, Sendable, Hashable {
    public let id: Int
    public let name: String
    public let memberCount: Int
    public let city: String?
    public let sportType: String?
    public let profileMedium: String?

    public init(id: Int, name: String, memberCount: Int, city: String?, sportType: String?, profileMedium: String?) {
        self.id = id
        self.name = name
        self.memberCount = memberCount
        self.city = city
        self.sportType = sportType
        self.profileMedium = profileMedium
    }

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
public struct SyncableClub: Codable, Identifiable, Sendable, Hashable {
    public let club: Club
    public var isEnabled: Bool

    public var id: Int { club.id }

    public init(club: Club, isEnabled: Bool) {
        self.club = club
        self.isEnabled = isEnabled
    }
}

import Foundation

/// Maps Strava activity types to appropriate emoji.
public enum ActivityEmoji {
    /// Returns the emoji for a given Strava activity type.
    public static func emoji(for activityType: String?) -> String {
        guard let activityType = activityType?.lowercased() else {
            return "📅"
        }

        switch activityType {
        case "ride", "cycling", "virtualride", "ebikeride", "gravel_ride":
            return "🚴"
        case "run", "running", "virtualrun", "trail_run":
            return "🏃"
        case "swim", "swimming":
            return "🏊"
        case "walk", "walking", "hike", "hiking":
            return "🥾"
        case "workout", "crossfit", "weight_training":
            return "🏋️"
        case "yoga":
            return "🧘"
        case "ski", "alpine_ski", "backcountry_ski", "nordic_ski":
            return "⛷️"
        case "snowboard":
            return "🏂"
        case "golf":
            return "🏌️"
        case "kayak", "kayaking", "canoe", "canoeing", "rowing":
            return "🚣"
        case "surf", "surfing", "windsurf", "kitesurf":
            return "🏄"
        case "skateboard", "skateboarding":
            return "🛹"
        case "rock_climb", "rock_climbing":
            return "🧗"
        case "tennis", "badminton", "squash", "racquetball", "pickleball":
            return "🎾"
        case "soccer", "football":
            return "⚽"
        case "basketball":
            return "🏀"
        case "ice_skate", "ice_skating":
            return "⛸️"
        default:
            return "📅"
        }
    }
}

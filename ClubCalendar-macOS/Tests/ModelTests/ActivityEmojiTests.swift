import Testing
@testable import ClubCalendarMac
@testable import ClubCalendarCore

@Suite("ActivityEmoji")
struct ActivityEmojiTests {
    @Test("Cycling activities return bike emoji", arguments: [
        "ride", "cycling", "virtualride", "ebikeride", "gravel_ride"
    ])
    func cyclingActivities(type: String) {
        #expect(ActivityEmoji.emoji(for: type) == "🚴")
    }

    @Test("Running activities return runner emoji", arguments: [
        "run", "running", "virtualrun", "trail_run"
    ])
    func runningActivities(type: String) {
        #expect(ActivityEmoji.emoji(for: type) == "🏃")
    }

    @Test("Swimming activities return swimmer emoji", arguments: ["swim", "swimming"])
    func swimmingActivities(type: String) {
        #expect(ActivityEmoji.emoji(for: type) == "🏊")
    }

    @Test("Hiking activities return boot emoji", arguments: [
        "walk", "walking", "hike", "hiking"
    ])
    func hikingActivities(type: String) {
        #expect(ActivityEmoji.emoji(for: type) == "🥾")
    }

    @Test("Case insensitivity", arguments: [
        ("RIDE", "🚴"),
        ("Ride", "🚴"),
        ("RUN", "🏃"),
        ("Run", "🏃")
    ])
    func caseInsensitivity(type: String, expected: String) {
        #expect(ActivityEmoji.emoji(for: type) == expected)
    }

    @Test("Nil returns calendar emoji")
    func nilReturnsCalendar() {
        #expect(ActivityEmoji.emoji(for: nil) == "📅")
    }

    @Test("Unknown activities return calendar emoji", arguments: [
        "unknown_activity", "", "xyz123"
    ])
    func unknownActivities(type: String) {
        #expect(ActivityEmoji.emoji(for: type) == "📅")
    }

    @Test("Winter sports emojis", arguments: [
        ("ski", "⛷️"),
        ("alpine_ski", "⛷️"),
        ("snowboard", "🏂"),
        ("ice_skate", "⛸️")
    ])
    func winterSports(type: String, expected: String) {
        #expect(ActivityEmoji.emoji(for: type) == expected)
    }

    @Test("Water sports emojis", arguments: [
        ("kayak", "🚣"),
        ("surf", "🏄"),
        ("rowing", "🚣")
    ])
    func waterSports(type: String, expected: String) {
        #expect(ActivityEmoji.emoji(for: type) == expected)
    }

    @Test("Workout emojis", arguments: [
        ("workout", "🏋️"),
        ("crossfit", "🏋️"),
        ("weight_training", "🏋️"),
        ("yoga", "🧘")
    ])
    func workoutEmojis(type: String, expected: String) {
        #expect(ActivityEmoji.emoji(for: type) == expected)
    }

    @Test("Ball sports emojis", arguments: [
        ("tennis", "🎾"),
        ("soccer", "⚽"),
        ("basketball", "🏀"),
        ("golf", "🏌️")
    ])
    func ballSports(type: String, expected: String) {
        #expect(ActivityEmoji.emoji(for: type) == expected)
    }

    @Test("Other activities", arguments: [
        ("skateboard", "🛹"),
        ("rock_climb", "🧗")
    ])
    func otherActivities(type: String, expected: String) {
        #expect(ActivityEmoji.emoji(for: type) == expected)
    }

    // Additional coverage tests

    @Test("Additional ski variants", arguments: [
        ("backcountry_ski", "⛷️"),
        ("nordic_ski", "⛷️")
    ])
    func additionalSkiVariants(type: String, expected: String) {
        #expect(ActivityEmoji.emoji(for: type) == expected)
    }

    @Test("Kayak variants", arguments: [
        ("kayaking", "🚣"),
        ("canoe", "🚣"),
        ("canoeing", "🚣")
    ])
    func kayakVariants(type: String, expected: String) {
        #expect(ActivityEmoji.emoji(for: type) == expected)
    }

    @Test("Surf variants", arguments: [
        ("surfing", "🏄"),
        ("windsurf", "🏄"),
        ("kitesurf", "🏄")
    ])
    func surfVariants(type: String, expected: String) {
        #expect(ActivityEmoji.emoji(for: type) == expected)
    }

    @Test("Rock climbing variants")
    func rockClimbingVariants() {
        #expect(ActivityEmoji.emoji(for: "rock_climbing") == "🧗")
    }

    @Test("Racquet sports", arguments: [
        ("badminton", "🎾"),
        ("squash", "🎾"),
        ("racquetball", "🎾"),
        ("pickleball", "🎾")
    ])
    func racquetSports(type: String, expected: String) {
        #expect(ActivityEmoji.emoji(for: type) == expected)
    }

    @Test("Football variants")
    func footballVariants() {
        #expect(ActivityEmoji.emoji(for: "football") == "⚽")
    }

    @Test("Skateboard variant")
    func skateboardVariant() {
        #expect(ActivityEmoji.emoji(for: "skateboarding") == "🛹")
    }

    @Test("Ice skating variant")
    func iceSkatingVariant() {
        #expect(ActivityEmoji.emoji(for: "ice_skating") == "⛸️")
    }

    @Test("Empty string returns calendar emoji")
    func emptyStringReturnsCalendar() {
        #expect(ActivityEmoji.emoji(for: "") == "📅")
    }

    @Test("Mixed case activity types", arguments: [
        ("VIRTUALRIDE", "🚴"),
        ("VirtualRun", "🏃"),
        ("SWIMMING", "🏊"),
        ("Walking", "🥾"),
        ("YOGA", "🧘")
    ])
    func mixedCaseActivityTypes(type: String, expected: String) {
        #expect(ActivityEmoji.emoji(for: type) == expected)
    }
}

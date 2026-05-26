import Testing
import Foundation
@testable import ClubCalendar

@Suite("ClubEvent Model")
struct ClubEventTests {
    @Test("Event decodes from Strava JSON")
    func eventDecodesFromJSON() throws {
        let json = """
        {
            "id": 54321,
            "title": "Morning Ride",
            "club_name": "BikeClub",
            "description": "Join us for a morning ride",
            "activity_type": "Ride",
            "start_datetime": "2025-01-25T10:00:00Z",
            "address": "Central Park",
            "private": false,
            "organizing_athlete": {
                "id": 111,
                "firstname": "John",
                "lastname": "Doe"
            }
        }
        """

        let decoder = JSONDecoder()

        let data = json.data(using: .utf8)!
        let event = try decoder.decode(ClubEvent.self, from: data)

        #expect(event.id == 54321)
        #expect(event.title == "Morning Ride")
        #expect(event.clubName == "BikeClub")
        #expect(event.description == "Join us for a morning ride")
        #expect(event.activityType == "Ride")
        #expect(event.address == "Central Park")
        #expect(event.privateEvent == false)
        #expect(event.organizingAthlete?.fullName == "John Doe")
    }

    @Test("Event decodes from real Strava API format")
    func eventDecodesFromRealAPIFormat() throws {
        let json = """
        {
            "id": 54321,
            "resource_state": 2,
            "title": "Morning Ride",
            "description": "Join us for a morning ride",
            "activity_type": "Ride",
            "club": {
                "id": 123,
                "name": "BikeClub",
                "sport_type": "cycling"
            },
            "organizing_athlete": {
                "id": 111,
                "firstname": "John",
                "lastname": "Doe"
            },
            "upcoming_occurrences": [
                "2025-01-25T10:00:00Z",
                "2025-02-01T10:00:00Z"
            ],
            "zone": "Europe/Amsterdam",
            "address": "Central Park",
            "private": false,
            "women_only": false,
            "skill_levels": 1,
            "terrain": 0
        }
        """

        let data = json.data(using: .utf8)!
        let event = try JSONDecoder().decode(ClubEvent.self, from: data)

        #expect(event.id == 54321)
        #expect(event.title == "Morning Ride")
        #expect(event.clubName == "BikeClub")
        #expect(event.clubId == 123)
        #expect(event.description == "Join us for a morning ride")
        #expect(event.activityType == "Ride")
        #expect(event.address == "Central Park")
        #expect(event.privateEvent == false)
        #expect(event.organizingAthlete?.fullName == "John Doe")
        #expect(event.stravaURL?.absoluteString == "https://www.strava.com/clubs/123/group_events/54321")
    }

    @Test("Activity emoji mapping", arguments: [
        ("Ride", "🚴"),
        ("ride", "🚴"),
        ("Run", "🏃"),
        ("Swim", "🏊"),
        ("Hike", "🥾"),
        ("Yoga", "🧘"),
        ("Unknown", "📅")
    ])
    func activityEmojiMapping(activityType: String, expectedEmoji: String) {
        let event = ClubEvent(
            id: 1,
            title: "Test",
            clubName: "Club",
            description: nil,
            activityType: activityType,
            startDatetime: Date(),
            address: nil,
            privateEvent: nil,
            organizingAthlete: nil,
            routeId: nil
        )
        #expect(event.activityEmoji == expectedEmoji)
    }

    @Test("Nil activity type returns calendar emoji")
    func nilActivityType() {
        let event = ClubEvent(
            id: 1,
            title: "Test",
            clubName: "Club",
            description: nil,
            activityType: nil,
            startDatetime: Date(),
            address: nil,
            privateEvent: nil,
            organizingAthlete: nil,
            routeId: nil
        )
        #expect(event.activityEmoji == "📅")
    }

    @Test("Formatted title includes emoji")
    func formattedTitleIncludesEmoji() {
        let event = ClubEvent(
            id: 1,
            title: "Weekend Group Ride",
            clubName: "BikeClub",
            description: nil,
            activityType: "Ride",
            startDatetime: Date(),
            address: nil,
            privateEvent: nil,
            organizingAthlete: nil,
            routeId: nil
        )

        #expect(event.formattedTitle == "🚴 BikeClub: Weekend Group Ride")
    }

    @Test("Strava URL generation")
    func stravaURLGeneration() {
        let event = ClubEvent(
            id: 12345,
            title: "Test",
            clubName: "Club",
            clubId: 678,
            description: nil,
            activityType: nil,
            startDatetime: Date(),
            address: nil,
            privateEvent: nil,
            organizingAthlete: nil,
            routeId: nil
        )

        #expect(event.stravaURL?.absoluteString == "https://www.strava.com/clubs/678/group_events/12345")
    }

    @Test("Event with all fields")
    func eventWithAllFields() throws {
        let json = """
        {
            "id": 99999,
            "title": "Full Event",
            "club_name": "Complete Club",
            "description": "A complete event with all fields",
            "activity_type": "Run",
            "start_datetime": "2025-06-15T08:30:00Z",
            "address": "123 Main Street",
            "private": true,
            "organizing_athlete": {
                "id": 222,
                "firstname": "Jane",
                "lastname": "Smith"
            },
            "route_id": 789
        }
        """

        let decoder = JSONDecoder()

        let data = json.data(using: .utf8)!
        let event = try decoder.decode(ClubEvent.self, from: data)

        #expect(event.routeId == 789)
        #expect(event.privateEvent == true)
        #expect(event.organizingAthlete?.id == 222)
    }

    @Test("Athlete full name variations")
    func athleteFullNameVariations() {
        let athleteWithBoth = Athlete(id: 1, firstName: "John", lastName: "Doe")
        #expect(athleteWithBoth.fullName == "John Doe")

        let athleteFirstOnly = Athlete(id: 2, firstName: "Jane", lastName: nil)
        #expect(athleteFirstOnly.fullName == "Jane")

        let athleteLastOnly = Athlete(id: 3, firstName: nil, lastName: "Smith")
        #expect(athleteLastOnly.fullName == "Smith")

        let athleteNoName = Athlete(id: 4, firstName: nil, lastName: nil)
        #expect(athleteNoName.fullName == "")
    }

    // MARK: - ClubEvent Encoding/Decoding Round Trip Tests

    @Test("ClubEvent encodes and decodes correctly")
    func clubEventRoundTrip() throws {
        let original = ClubEvent(
            id: 12345,
            title: "Round Trip Event",
            clubName: "Test Club",
            description: "A test event description",
            activityType: "Ride",
            startDatetime: Date(timeIntervalSince1970: 1706180400),
            address: "123 Test Street",
            privateEvent: true,
            organizingAthlete: Athlete(id: 1, firstName: "Test", lastName: "Organizer"),
            routeId: 789
        )

        let encoder = JSONEncoder()
        let decoder = JSONDecoder()

        let data = try encoder.encode(original)
        let decoded = try decoder.decode(ClubEvent.self, from: data)

        #expect(decoded.id == original.id)
        #expect(decoded.title == original.title)
        #expect(decoded.clubName == original.clubName)
        #expect(decoded.description == original.description)
        #expect(decoded.activityType == original.activityType)
        #expect(decoded.address == original.address)
        #expect(decoded.privateEvent == original.privateEvent)
        #expect(decoded.organizingAthlete?.fullName == original.organizingAthlete?.fullName)
        #expect(decoded.routeId == original.routeId)
    }

    @Test("ClubEvent with nil fields encodes and decodes correctly")
    func clubEventWithNilFieldsRoundTrip() throws {
        let original = ClubEvent(
            id: 1,
            title: "Minimal Event",
            clubName: "Club",
            description: nil,
            activityType: nil,
            startDatetime: Date(timeIntervalSince1970: 1706180400),
            address: nil,
            privateEvent: nil,
            organizingAthlete: nil,
            routeId: nil
        )

        let encoder = JSONEncoder()
        let decoder = JSONDecoder()

        let data = try encoder.encode(original)
        let decoded = try decoder.decode(ClubEvent.self, from: data)

        #expect(decoded.id == original.id)
        #expect(decoded.title == original.title)
        #expect(decoded.description == nil)
        #expect(decoded.activityType == nil)
        #expect(decoded.address == nil)
        #expect(decoded.privateEvent == nil)
        #expect(decoded.organizingAthlete == nil)
        #expect(decoded.routeId == nil)
    }

    // MARK: - Athlete Encoding/Decoding Tests

    @Test("Athlete encodes and decodes correctly")
    func athleteRoundTrip() throws {
        let original = Athlete(id: 12345, firstName: "John", lastName: "Doe")

        let encoder = JSONEncoder()
        let decoder = JSONDecoder()

        let data = try encoder.encode(original)
        let decoded = try decoder.decode(Athlete.self, from: data)

        #expect(decoded.id == original.id)
        #expect(decoded.firstName == original.firstName)
        #expect(decoded.lastName == original.lastName)
        #expect(decoded.fullName == original.fullName)
    }

    @Test("Athlete with nil names encodes and decodes correctly")
    func athleteWithNilNamesRoundTrip() throws {
        let original = Athlete(id: 1, firstName: nil, lastName: nil)

        let encoder = JSONEncoder()
        let decoder = JSONDecoder()

        let data = try encoder.encode(original)
        let decoded = try decoder.decode(Athlete.self, from: data)

        #expect(decoded.id == original.id)
        #expect(decoded.firstName == nil)
        #expect(decoded.lastName == nil)
        #expect(decoded.fullName == "")
    }

    // MARK: - ClubEvent Hashable Tests

    @Test("ClubEvent is Hashable")
    func clubEventIsHashable() {
        let fixedDate = Date(timeIntervalSince1970: 1706180400)  // Fixed date for consistent hashing
        let event1 = ClubEvent(
            id: 1, title: "Event", clubName: "Club",
            description: nil, activityType: nil,
            startDatetime: fixedDate, address: nil,
            privateEvent: nil, organizingAthlete: nil, routeId: nil
        )
        let event2 = ClubEvent(
            id: 1, title: "Event", clubName: "Club",
            description: nil, activityType: nil,
            startDatetime: fixedDate, address: nil,
            privateEvent: nil, organizingAthlete: nil, routeId: nil
        )
        let event3 = ClubEvent(
            id: 2, title: "Different", clubName: "Club",
            description: nil, activityType: nil,
            startDatetime: fixedDate, address: nil,
            privateEvent: nil, organizingAthlete: nil, routeId: nil
        )

        var set = Set<ClubEvent>()
        set.insert(event1)
        set.insert(event2)
        set.insert(event3)
        #expect(set.count == 2)
    }

    // MARK: - Formatted Title Tests

    @Test("Formatted title with various activity types")
    func formattedTitleWithVariousActivityTypes() {
        let testCases: [(String?, String)] = [
            ("Ride", "🚴 Club: Test"),
            ("Run", "🏃 Club: Test"),
            ("Swim", "🏊 Club: Test"),
            (nil, "📅 Club: Test")
        ]

        for (activityType, expectedPrefix) in testCases {
            let event = ClubEvent(
                id: 1, title: "Test", clubName: "Club",
                description: nil, activityType: activityType,
                startDatetime: Date(), address: nil,
                privateEvent: nil, organizingAthlete: nil, routeId: nil
            )
            #expect(event.formattedTitle == expectedPrefix)
        }
    }

    // MARK: - Strava URL Tests

    @Test("Strava URL is generated correctly for various IDs")
    func stravaURLForVariousIDs() {
        let testIDs = [1, 100, 12345, 999999, 0]

        for id in testIDs {
            let event = ClubEvent(
                id: id, title: "Test", clubName: "Club", clubId: 42,
                description: nil, activityType: nil,
                startDatetime: Date(), address: nil,
                privateEvent: nil, organizingAthlete: nil, routeId: nil
            )
            #expect(event.stravaURL?.absoluteString == "https://www.strava.com/clubs/42/group_events/\(id)")
        }
    }

    // MARK: - Array Sorting Tests

    @Test("ClubEvent array can be sorted by date")
    func clubEventArraySortingByDate() {
        let date1 = Date(timeIntervalSince1970: 1000)
        let date2 = Date(timeIntervalSince1970: 2000)
        let date3 = Date(timeIntervalSince1970: 3000)

        let events = [
            ClubEvent(id: 3, title: "C", clubName: "Club", description: nil, activityType: nil, startDatetime: date3, address: nil, privateEvent: nil, organizingAthlete: nil, routeId: nil),
            ClubEvent(id: 1, title: "A", clubName: "Club", description: nil, activityType: nil, startDatetime: date1, address: nil, privateEvent: nil, organizingAthlete: nil, routeId: nil),
            ClubEvent(id: 2, title: "B", clubName: "Club", description: nil, activityType: nil, startDatetime: date2, address: nil, privateEvent: nil, organizingAthlete: nil, routeId: nil)
        ]

        let sorted = events.sorted { $0.startDatetime < $1.startDatetime }

        #expect(sorted[0].id == 1)
        #expect(sorted[1].id == 2)
        #expect(sorted[2].id == 3)
    }
}

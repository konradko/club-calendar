import Testing
import Foundation
@testable import ClubCalendar

@Suite("ClubEvent Extended Tests")
struct ClubEventExtendedTests {
    // MARK: - Helper to create ClubEvent

    private func createEvent(
        id: Int = 1,
        title: String = "Test Event",
        clubName: String = "Test Club",
        description: String? = nil,
        activityType: String? = nil,
        startDatetime: Date = Date(),
        address: String? = nil,
        privateEvent: Bool? = nil,
        organizingAthlete: Athlete? = nil,
        routeId: Int? = nil
    ) -> ClubEvent {
        ClubEvent(
            id: id,
            title: title,
            clubName: clubName,
            description: description,
            activityType: activityType,
            startDatetime: startDatetime,
            address: address,
            privateEvent: privateEvent,
            organizingAthlete: organizingAthlete,
            routeId: routeId
        )
    }

    // MARK: - Formatted Title Tests

    @Test("formattedTitle with activity type")
    func formattedTitleWithActivityType() {
        let event = createEvent(
            title: "Morning Ride",
            clubName: "BikeClub",
            activityType: "Ride"
        )

        let title = event.formattedTitle
        #expect(title.contains("Morning Ride"))
        #expect(title.contains("BikeClub"))
    }

    @Test("formattedTitle without activity type")
    func formattedTitleWithoutActivityType() {
        let event = createEvent(
            title: "Club Meetup",
            clubName: "RunClub",
            activityType: nil
        )

        let title = event.formattedTitle
        #expect(title.contains("Club Meetup"))
        #expect(title.contains("RunClub"))
    }

    @Test("formattedTitle with various activity types", arguments: [
        "Ride", "Run", "Swim", "Walk", "Hike", "Yoga", "Workout", "CrossFit"
    ])
    func formattedTitleWithVariousActivityTypes(activityType: String) {
        let event = createEvent(activityType: activityType)

        let title = event.formattedTitle
        #expect(!title.isEmpty)
    }

    // MARK: - Activity Emoji Tests

    @Test("activityEmoji returns correct emoji for Ride")
    func activityEmojiForRide() {
        let event = createEvent(activityType: "Ride")
        #expect(event.activityEmoji == "🚴")
    }

    @Test("activityEmoji returns correct emoji for Run")
    func activityEmojiForRun() {
        let event = createEvent(activityType: "Run")
        #expect(event.activityEmoji == "🏃")
    }

    @Test("activityEmoji returns default for unknown activity")
    func activityEmojiForUnknown() {
        let event = createEvent(activityType: "UnknownActivity")
        #expect(event.activityEmoji == "📅")
    }

    @Test("activityEmoji returns default for nil activity")
    func activityEmojiForNil() {
        let event = createEvent(activityType: nil)
        #expect(event.activityEmoji == "📅")
    }

    // MARK: - Strava URL Tests

    @Test("stravaURL returns correct URL")
    func stravaURLReturnsCorrectURL() {
        let event = createEvent(id: 12345)

        let url = event.stravaURL
        #expect(url != nil)
        #expect(url?.absoluteString.contains("strava.com") == true)
        #expect(url?.absoluteString.contains("12345") == true)
    }

    @Test("stravaURL for various event IDs", arguments: [1, 100, 999999])
    func stravaURLForVariousEventIDs(eventId: Int) {
        let event = createEvent(id: eventId)

        let url = event.stravaURL
        #expect(url != nil)
        #expect(url?.absoluteString.contains("\(eventId)") == true)
    }

    @Test("stravaURL path structure")
    func stravaURLPathStructure() {
        let event = createEvent(id: 42)

        let url = event.stravaURL
        #expect(url?.host?.contains("strava.com") == true)
        #expect(url?.path.contains("/group_events/") == true)
        #expect(url?.path.hasSuffix("/42") == true)
    }

    // MARK: - Athlete Tests

    @Test("Athlete full name")
    func athleteFullName() {
        let athlete = Athlete(id: 1, firstName: "John", lastName: "Smith")
        #expect(athlete.fullName == "John Smith")
    }

    @Test("Athlete with only first name")
    func athleteOnlyFirstName() {
        let athlete = Athlete(id: 1, firstName: "Jane", lastName: nil)
        #expect(athlete.fullName == "Jane")
    }

    @Test("Athlete with only last name")
    func athleteOnlyLastName() {
        let athlete = Athlete(id: 1, firstName: nil, lastName: "Doe")
        #expect(athlete.fullName == "Doe")
    }

    @Test("Athlete with no names")
    func athleteNoNames() {
        let athlete = Athlete(id: 1, firstName: nil, lastName: nil)
        #expect(athlete.fullName == "")
    }

    @Test("Athlete encodes and decodes")
    func athleteEncodesAndDecodes() throws {
        let original = Athlete(id: 12345, firstName: "Test", lastName: "User")

        let encoder = JSONEncoder()
        let decoder = JSONDecoder()

        let data = try encoder.encode(original)
        let decoded = try decoder.decode(Athlete.self, from: data)

        #expect(decoded.id == original.id)
        #expect(decoded.firstName == original.firstName)
        #expect(decoded.lastName == original.lastName)
        #expect(decoded.fullName == original.fullName)
    }

    @Test("Athlete is Hashable")
    func athleteIsHashable() {
        let athlete1 = Athlete(id: 1, firstName: "John", lastName: "Doe")
        let athlete2 = Athlete(id: 1, firstName: "John", lastName: "Doe")
        let athlete3 = Athlete(id: 2, firstName: "Jane", lastName: "Doe")

        #expect(athlete1 == athlete2)
        #expect(athlete1 != athlete3)

        var set = Set<Athlete>()
        set.insert(athlete1)
        set.insert(athlete2)
        #expect(set.count == 1)
    }

    // MARK: - ClubEvent with Athlete Tests

    @Test("ClubEvent with organizing athlete")
    func clubEventWithOrganizingAthlete() {
        let athlete = Athlete(id: 1, firstName: "Organizer", lastName: "Name")
        let event = createEvent(organizingAthlete: athlete)

        #expect(event.organizingAthlete != nil)
        #expect(event.organizingAthlete?.fullName == "Organizer Name")
    }

    @Test("ClubEvent without organizing athlete")
    func clubEventWithoutOrganizingAthlete() {
        let event = createEvent(organizingAthlete: nil)
        #expect(event.organizingAthlete == nil)
    }

    // MARK: - Description Tests

    @Test("ClubEvent with description")
    func clubEventWithDescription() {
        let event = createEvent(description: "This is a detailed event description.")
        #expect(event.description == "This is a detailed event description.")
    }

    @Test("ClubEvent with empty description")
    func clubEventWithEmptyDescription() {
        let event = createEvent(description: "")
        #expect(event.description == "")
    }

    // MARK: - Address Tests

    @Test("ClubEvent with address")
    func clubEventWithAddress() {
        let event = createEvent(address: "123 Test Street, City")
        #expect(event.address == "123 Test Street, City")
    }

    @Test("ClubEvent without address")
    func clubEventWithoutAddress() {
        let event = createEvent(address: nil)
        #expect(event.address == nil)
    }

    // MARK: - Private Event Tests

    @Test("ClubEvent private event true")
    func clubEventPrivateTrue() {
        let event = createEvent(privateEvent: true)
        #expect(event.privateEvent == true)
    }

    @Test("ClubEvent private event false")
    func clubEventPrivateFalse() {
        let event = createEvent(privateEvent: false)
        #expect(event.privateEvent == false)
    }

    @Test("ClubEvent private event nil")
    func clubEventPrivateNil() {
        let event = createEvent(privateEvent: nil)
        #expect(event.privateEvent == nil)
    }

    // MARK: - Route ID Tests

    @Test("ClubEvent with route ID")
    func clubEventWithRouteId() {
        let event = createEvent(routeId: 12345)
        #expect(event.routeId == 12345)
    }

    @Test("ClubEvent without route ID")
    func clubEventWithoutRouteId() {
        let event = createEvent(routeId: nil)
        #expect(event.routeId == nil)
    }

    // MARK: - Identifiable Conformance

    @Test("ClubEvent Identifiable conformance")
    func clubEventIdentifiable() {
        let event1 = createEvent(id: 1, title: "Event 1")
        let event2 = createEvent(id: 2, title: "Event 2")

        #expect(event1.id != event2.id)
    }

    // MARK: - Hashable Conformance

    @Test("ClubEvent is Hashable")
    func clubEventIsHashable() {
        let fixedDate = Date(timeIntervalSince1970: 1706180400)
        let event1 = createEvent(id: 1, title: "Event", startDatetime: fixedDate)
        let event2 = createEvent(id: 1, title: "Event", startDatetime: fixedDate)
        let event3 = createEvent(id: 2, title: "Event", startDatetime: fixedDate)

        #expect(event1 == event2)
        #expect(event1 != event3)

        var set = Set<ClubEvent>()
        set.insert(event1)
        set.insert(event2)
        #expect(set.count == 1)
    }

    // MARK: - Sendable Conformance

    @Test("ClubEvent Sendable conformance")
    func clubEventSendable() async {
        let athlete = Athlete(id: 1, firstName: "Test", lastName: "User")
        let event = createEvent(
            id: 1,
            title: "Test",
            description: "Test",
            activityType: "Ride",
            address: "Address",
            organizingAthlete: athlete
        )

        let task = Task { @Sendable in
            return event.id
        }

        let id = await task.value
        #expect(id == 1)
    }

    @Test("Athlete Sendable conformance")
    func athleteSendable() async {
        let athlete = Athlete(id: 1, firstName: "Test", lastName: "User")

        let task = Task { @Sendable in
            return athlete.fullName
        }

        let name = await task.value
        #expect(name == "Test User")
    }

    // MARK: - JSON Encoding/Decoding

    @Test("ClubEvent minimal round-trip")
    func clubEventMinimalRoundTrip() throws {
        let original = createEvent(id: 1, title: "Test", clubName: "Club")

        let data = try JSONEncoder().encode(original)
        let decoded = try JSONDecoder().decode(ClubEvent.self, from: data)

        #expect(decoded.id == original.id)
        #expect(decoded.title == original.title)
        #expect(decoded.clubName == original.clubName)
    }

    @Test("ClubEvent full round-trip with all fields")
    func clubEventFullRoundTrip() throws {
        let athlete = Athlete(id: 100, firstName: "Test", lastName: "Organizer")
        let original = createEvent(
            id: 12345,
            title: "Complete Event",
            clubName: "Full Club",
            description: "Full description",
            activityType: "Ride",
            startDatetime: Date(timeIntervalSince1970: 1706180400),
            address: "Full Address",
            privateEvent: true,
            organizingAthlete: athlete,
            routeId: 67890
        )

        let data = try JSONEncoder().encode(original)
        let decoded = try JSONDecoder().decode(ClubEvent.self, from: data)

        #expect(decoded.id == original.id)
        #expect(decoded.title == original.title)
        #expect(decoded.clubName == original.clubName)
        #expect(decoded.activityType == original.activityType)
        #expect(decoded.description == original.description)
        #expect(decoded.address == original.address)
        #expect(decoded.privateEvent == original.privateEvent)
        #expect(decoded.routeId == original.routeId)
        #expect(decoded.organizingAthlete?.id == original.organizingAthlete?.id)
        #expect(decoded.organizingAthlete?.firstName == original.organizingAthlete?.firstName)
        #expect(decoded.organizingAthlete?.lastName == original.organizingAthlete?.lastName)
    }
}

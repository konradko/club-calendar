import Testing
import Foundation
@testable import ClubCalendar

@Suite("CalendarService")
struct CalendarServiceTests {
    // MARK: - CalendarError Tests

    @Test("Calendar error descriptions are meaningful")
    func calendarErrorDescriptions() {
        let errors: [CalendarError] = [
            .accessDenied,
            .accessRestricted,
            .calendarNotFound,
            .eventCreationFailed,
            .eventUpdateFailed,
            .unknownError(NSError(domain: "TestDomain", code: 123, userInfo: [NSLocalizedDescriptionKey: "Test error"]))
        ]

        for error in errors {
            #expect(error.errorDescription != nil)
            #expect(!error.errorDescription!.isEmpty)
        }
    }

    @Test("Calendar error descriptions contain relevant information")
    func calendarErrorDescriptionsContainRelevantInfo() {
        #expect(CalendarError.accessDenied.errorDescription?.contains("denied") == true)
        #expect(CalendarError.accessRestricted.errorDescription?.contains("restricted") == true)
        #expect(CalendarError.calendarNotFound.errorDescription?.contains("calendar") == true)
        #expect(CalendarError.eventCreationFailed.errorDescription?.contains("create") == true)
        #expect(CalendarError.eventUpdateFailed.errorDescription?.contains("update") == true)

        let underlying = NSError(domain: "Test", code: 1, userInfo: [NSLocalizedDescriptionKey: "Underlying error"])
        let unknownError = CalendarError.unknownError(underlying)
        #expect(unknownError.errorDescription?.contains("Underlying error") == true)
    }

    // MARK: - CalendarAccessStatus Tests

    @Test("Calendar access status values")
    func calendarAccessStatusValues() {
        let statuses: [CalendarAccessStatus] = [.authorized, .denied, .restricted, .notDetermined]
        #expect(statuses.count == 4)

        // Verify each status is distinct
        let statusSet = Set(statuses.map { "\($0)" })
        #expect(statusSet.count == 4)
    }

    // MARK: - SyncResult Tests

    @Test("SyncResult with all zeros")
    func syncResultWithAllZeros() {
        let result = SyncResult(created: 0, updated: 0, cancelled: 0)
        #expect(result.totalChanges == 0)
        #expect(result.hasChanges == false)
        #expect(result.summary == "No changes")
    }

    @Test("SyncResult with only created")
    func syncResultWithOnlyCreated() {
        let result = SyncResult(created: 5, updated: 0, cancelled: 0)
        #expect(result.totalChanges == 5)
        #expect(result.hasChanges == true)
        #expect(result.summary == "5 created")
    }

    @Test("SyncResult with only updated")
    func syncResultWithOnlyUpdated() {
        let result = SyncResult(created: 0, updated: 3, cancelled: 0)
        #expect(result.totalChanges == 3)
        #expect(result.hasChanges == true)
        #expect(result.summary == "3 updated")
    }

    @Test("SyncResult with only cancelled")
    func syncResultWithOnlyCancelled() {
        let result = SyncResult(created: 0, updated: 0, cancelled: 2)
        #expect(result.totalChanges == 2)
        #expect(result.hasChanges == true)
        #expect(result.summary == "2 cancelled")
    }

    @Test("SyncResult with all types")
    func syncResultWithAllTypes() {
        let result = SyncResult(created: 3, updated: 2, cancelled: 1)
        #expect(result.totalChanges == 6)
        #expect(result.hasChanges == true)
        #expect(result.summary == "3 created, 2 updated, 1 cancelled")
    }

    @Test("SyncResult with two types")
    func syncResultWithTwoTypes() {
        let result1 = SyncResult(created: 1, updated: 2, cancelled: 0)
        #expect(result1.summary == "1 created, 2 updated")

        let result2 = SyncResult(created: 1, updated: 0, cancelled: 3)
        #expect(result2.summary == "1 created, 3 cancelled")

        let result3 = SyncResult(created: 0, updated: 2, cancelled: 3)
        #expect(result3.summary == "2 updated, 3 cancelled")
    }

    @Test("SyncResult with large numbers")
    func syncResultWithLargeNumbers() {
        let result = SyncResult(created: 100, updated: 50, cancelled: 25)
        #expect(result.totalChanges == 175)
        #expect(result.summary == "100 created, 50 updated, 25 cancelled")
    }

    // MARK: - CalendarEventData Tests

    @Test("CalendarEventData is Sendable")
    func calendarEventDataIsSendable() async {
        // Create CalendarEventData and pass it across actor boundaries
        let eventData = CalendarEventData(
            id: "test-id-123",
            title: "Test Event",
            startDate: Date()
        )

        // Test that it can be used in async context
        let task = Task { @Sendable in
            return eventData.title
        }

        let title = await task.value
        #expect(title == "Test Event")
    }

    @Test("CalendarEventData stores correct values")
    func calendarEventDataStoresCorrectValues() {
        let testDate = Date(timeIntervalSince1970: 1706180400)  // 2024-01-25 10:00:00 UTC
        let eventData = CalendarEventData(
            id: "unique-event-id",
            title: "Morning Ride",
            startDate: testDate
        )

        #expect(eventData.id == "unique-event-id")
        #expect(eventData.title == "Morning Ride")
        #expect(eventData.startDate == testDate)
    }

    @Test("CalendarEventData Identifiable conformance")
    func calendarEventDataIdentifiable() {
        let event1 = CalendarEventData(id: "id-1", title: "Event 1", startDate: Date())
        let event2 = CalendarEventData(id: "id-2", title: "Event 2", startDate: Date())
        let event3 = CalendarEventData(id: "id-1", title: "Different Title", startDate: Date())

        // IDs should be used for identity
        #expect(event1.id != event2.id)
        #expect(event1.id == event3.id)
    }

    // MARK: - Additional CalendarEventData Tests

    @Test("CalendarEventData with various date values")
    func calendarEventDataWithVariousDates() {
        let dates = [
            Date(timeIntervalSince1970: 0),
            Date(timeIntervalSince1970: 1000000000),
            Date(),
            Date.distantFuture,
            Date.distantPast
        ]

        for date in dates {
            let event = CalendarEventData(id: "test", title: "Test", startDate: date)
            #expect(event.startDate == date)
        }
    }

    @Test("CalendarEventData with empty title")
    func calendarEventDataWithEmptyTitle() {
        let event = CalendarEventData(id: "test", title: "", startDate: Date())
        #expect(event.title == "")
    }

    @Test("CalendarEventData with long title")
    func calendarEventDataWithLongTitle() {
        let longTitle = String(repeating: "A", count: 1000)
        let event = CalendarEventData(id: "test", title: longTitle, startDate: Date())
        #expect(event.title == longTitle)
        #expect(event.title.count == 1000)
    }

    @Test("CalendarEventData with special characters in title")
    func calendarEventDataWithSpecialCharacters() {
        let specialTitle = "Event 🎉 with émojis & speciál chars <>&\""
        let event = CalendarEventData(id: "test", title: specialTitle, startDate: Date())
        #expect(event.title == specialTitle)
    }

    @Test("CalendarEventData with UUID-style id")
    func calendarEventDataWithUUID() {
        let uuid = UUID().uuidString
        let event = CalendarEventData(id: uuid, title: "Test", startDate: Date())
        #expect(event.id == uuid)
    }

    // MARK: - Additional SyncResult Tests

    @Test("SyncResult individual property access")
    func syncResultIndividualPropertyAccess() {
        let result = SyncResult(created: 10, updated: 20, cancelled: 30)
        #expect(result.created == 10)
        #expect(result.updated == 20)
        #expect(result.cancelled == 30)
    }

    // MARK: - CalendarAccessStatus Tests

    @Test("CalendarAccessStatus all cases exist")
    func calendarAccessStatusAllCases() {
        let authorized = CalendarAccessStatus.authorized
        let denied = CalendarAccessStatus.denied
        let restricted = CalendarAccessStatus.restricted
        let notDetermined = CalendarAccessStatus.notDetermined

        // Verify they're all distinct
        #expect(String(describing: authorized) != String(describing: denied))
        #expect(String(describing: denied) != String(describing: restricted))
        #expect(String(describing: restricted) != String(describing: notDetermined))
    }

    @Test("CalendarAccessStatus Sendable conformance")
    func calendarAccessStatusSendable() async {
        let status: CalendarAccessStatus = .authorized

        let task = Task { @Sendable in
            return status
        }

        let result = await task.value
        #expect(String(describing: result) == String(describing: CalendarAccessStatus.authorized))
    }
}

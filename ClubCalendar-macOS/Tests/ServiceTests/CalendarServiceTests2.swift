import Testing
import Foundation
@testable import ClubCalendarMac
@testable import ClubCalendarCore

@Suite("Calendar Types Tests")
struct CalendarTypesTests {
    // MARK: - CalendarAccessStatus Tests

    @Test("CalendarAccessStatus cases exist")
    func calendarAccessStatusCases() {
        let authorized = CalendarAccessStatus.authorized
        let denied = CalendarAccessStatus.denied
        let restricted = CalendarAccessStatus.restricted
        let notDetermined = CalendarAccessStatus.notDetermined

        #expect(authorized == .authorized)
        #expect(denied == .denied)
        #expect(restricted == .restricted)
        #expect(notDetermined == .notDetermined)
    }

    // MARK: - CalendarError Tests

    @Test("CalendarError descriptions are correct")
    func calendarErrorDescriptions() {
        #expect(CalendarError.accessDenied.errorDescription?.contains("access denied") == true)
        #expect(CalendarError.accessRestricted.errorDescription?.contains("restricted") == true)
        #expect(CalendarError.calendarNotFound.errorDescription?.contains("find or create") == true)
        #expect(CalendarError.eventCreationFailed.errorDescription?.contains("create") == true)
        #expect(CalendarError.eventUpdateFailed.errorDescription?.contains("update") == true)

        struct TestError: Error, LocalizedError {
            var errorDescription: String? { "underlying error" }
        }
        let unknownError = CalendarError.unknownError(TestError())
        #expect(unknownError.errorDescription?.contains("underlying error") == true)
    }

    @Test("CalendarError is Sendable")
    func calendarErrorIsSendable() {
        let error: any Sendable = CalendarError.accessDenied
        #expect(error is CalendarError)
    }

    // MARK: - SyncResult Tests

    @Test("SyncResult initializes correctly")
    func syncResultInit() {
        let result = SyncResult(created: 5, updated: 3, cancelled: 2)

        #expect(result.created == 5)
        #expect(result.updated == 3)
        #expect(result.cancelled == 2)
    }

    @Test("SyncResult totalChanges is correct")
    func syncResultTotalChanges() {
        let result = SyncResult(created: 5, updated: 3, cancelled: 2)
        #expect(result.totalChanges == 10)

        let noChanges = SyncResult(created: 0, updated: 0, cancelled: 0)
        #expect(noChanges.totalChanges == 0)
    }

    @Test("SyncResult hasChanges is correct")
    func syncResultHasChanges() {
        let hasChanges = SyncResult(created: 1, updated: 0, cancelled: 0)
        #expect(hasChanges.hasChanges == true)

        let noChanges = SyncResult(created: 0, updated: 0, cancelled: 0)
        #expect(noChanges.hasChanges == false)
    }

    @Test("SyncResult summary is correct")
    func syncResultSummary() {
        let allChanges = SyncResult(created: 5, updated: 3, cancelled: 2)
        #expect(allChanges.summary.contains("5 created"))
        #expect(allChanges.summary.contains("3 updated"))
        #expect(allChanges.summary.contains("2 cancelled"))

        let onlyCreated = SyncResult(created: 1, updated: 0, cancelled: 0)
        #expect(onlyCreated.summary == "1 created")

        let noChanges = SyncResult(created: 0, updated: 0, cancelled: 0)
        #expect(noChanges.summary == "No changes")
    }

    @Test("SyncResult is Sendable")
    func syncResultIsSendable() {
        let result: any Sendable = SyncResult(created: 1, updated: 0, cancelled: 0)
        #expect(result is SyncResult)
    }

    // MARK: - CalendarEventData Tests

    @Test("CalendarEventData initializes with parameters")
    func calendarEventDataInit() {
        let date = Date()
        let eventData = CalendarEventData(id: "test-id", title: "Test Event", startDate: date)

        #expect(eventData.id == "test-id")
        #expect(eventData.title == "Test Event")
        #expect(eventData.startDate == date)
    }

    @Test("CalendarEventData is Identifiable")
    func calendarEventDataIdentifiable() {
        let eventData1 = CalendarEventData(id: "id1", title: "Event 1", startDate: Date())
        let eventData2 = CalendarEventData(id: "id2", title: "Event 2", startDate: Date())

        #expect(eventData1.id != eventData2.id)
    }

    @Test("CalendarEventData is Sendable")
    func calendarEventDataSendable() {
        let eventData: any Sendable = CalendarEventData(id: "test", title: "Test", startDate: Date())
        #expect(eventData is CalendarEventData)
    }

    // MARK: - CalendarService Initialization Tests

    @Test("CalendarService initializes with default calendar name")
    func calendarServiceInitDefault() async {
        let service = CalendarService()
        // Just verify it initializes without crashing
        let _ = await service.checkAccessStatus()
    }

    @Test("CalendarService initializes with custom calendar name")
    func calendarServiceInitCustomName() async {
        let service = CalendarService(calendarName: "My Custom Calendar")
        let _ = await service.checkAccessStatus()
    }

    // MARK: - CalendarService Access Status Tests

    @Test("CalendarService checkAccessStatus returns a valid status")
    func calendarServiceCheckAccessStatus() async {
        let service = CalendarService()
        let status = await service.checkAccessStatus()

        // Status should be one of the valid values
        let validStatuses: [CalendarAccessStatus] = [.authorized, .denied, .restricted, .notDetermined]
        #expect(validStatuses.contains(status))
    }
}

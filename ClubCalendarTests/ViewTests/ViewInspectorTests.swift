import Testing
import SwiftUI
import ViewInspector
@testable import ClubCalendar

// ViewInspector 0.10+ no longer requires Inspectable conformances

@Suite("ViewInspector Content Tests")
struct ViewInspectorTests {
    // MARK: - EventRow Tests

    @Test("EventRow displays event title")
    @MainActor
    func eventRowDisplaysTitle() throws {
        let event = CalendarEventData(
            id: "test-1",
            title: "Morning Ride",
            startDate: Date()
        )

        let view = EventRow(event: event)
        let inspected = try view.inspect()

        // EventRow renders the time and title as a single Button label string
        // (required for the NSMenu-backed MenuBarExtra), so assert on substring.
        let texts = inspected.findAll(ViewType.Text.self)
        let titleTexts = texts.compactMap { try? $0.string() }

        #expect(titleTexts.contains { $0.contains("Morning Ride") })
    }

    @Test("EventRow displays time")
    @MainActor
    func eventRowDisplaysTime() throws {
        let fixedDate = Date(timeIntervalSince1970: 1706180400)  // 10:00 AM UTC
        let event = CalendarEventData(
            id: "test-2",
            title: "Test Event",
            startDate: fixedDate
        )

        let view = EventRow(event: event)
        let inspected = try view.inspect()

        // Single combined label "HH:mm  Title". Verify the formatted time
        // substring appears in the rendered text.
        let texts = inspected.findAll(ViewType.Text.self)
            .compactMap { try? $0.string() }
        let formatter = DateFormatter()
        formatter.timeStyle = .short
        let expectedTime = formatter.string(from: fixedDate)
        #expect(texts.contains { $0.contains(expectedTime) })
    }

    @Test("EventRow is a button")
    @MainActor
    func eventRowIsButton() throws {
        let event = CalendarEventData(
            id: "test-3",
            title: "Clickable Event",
            startDate: Date()
        )

        let view = EventRow(event: event)
        let inspected = try view.inspect()

        // EventRow should be a button - if find succeeds, the button exists
        _ = try inspected.find(ViewType.Button.self)
        // If we reach here, button was found
    }

    // MARK: - ClubRow Tests

    @Test("ClubRow displays club name")
    @MainActor
    func clubRowDisplaysClubName() throws {
        let club = Club(
            id: 1,
            name: "Amsterdam Cycling Club",
            memberCount: 250,
            city: "Amsterdam",
            sportType: "cycling",
            profileMedium: nil
        )
        let syncable = SyncableClub(club: club, isEnabled: true)

        let view = ClubRow(syncableClub: syncable) { _ in }
        let inspected = try view.inspect()

        let texts = inspected.findAll(ViewType.Text.self)
        let textStrings = texts.compactMap { try? $0.string() }

        #expect(textStrings.contains("Amsterdam Cycling Club"))
    }

    @Test("ClubRow displays member count")
    @MainActor
    func clubRowDisplaysMemberCount() throws {
        let club = Club(
            id: 2,
            name: "Test Club",
            memberCount: 100,
            city: nil,
            sportType: nil,
            profileMedium: nil
        )
        let syncable = SyncableClub(club: club, isEnabled: true)

        let view = ClubRow(syncableClub: syncable) { _ in }
        let inspected = try view.inspect()

        let texts = inspected.findAll(ViewType.Text.self)
        let textStrings = texts.compactMap { try? $0.string() }

        let hasMemberCount = textStrings.contains { $0.contains("100") && $0.contains("members") }
        #expect(hasMemberCount)
    }

    @Test("ClubRow displays city when available")
    @MainActor
    func clubRowDisplaysCity() throws {
        let club = Club(
            id: 3,
            name: "City Club",
            memberCount: 50,
            city: "Berlin",
            sportType: nil,
            profileMedium: nil
        )
        let syncable = SyncableClub(club: club, isEnabled: true)

        let view = ClubRow(syncableClub: syncable) { _ in }
        let inspected = try view.inspect()

        let texts = inspected.findAll(ViewType.Text.self)
        let textStrings = texts.compactMap { try? $0.string() }

        #expect(textStrings.contains("Berlin"))
    }

    @Test("ClubRow has toggle")
    @MainActor
    func clubRowHasToggle() throws {
        let club = Club(
            id: 4,
            name: "Toggle Club",
            memberCount: 25,
            city: nil,
            sportType: nil,
            profileMedium: nil
        )
        let syncable = SyncableClub(club: club, isEnabled: true)

        let view = ClubRow(syncableClub: syncable) { _ in }
        let inspected = try view.inspect()

        // Should have a Toggle - if find succeeds, the toggle exists
        _ = try inspected.find(ViewType.Toggle.self)
        // If we reach here, toggle was found
    }

    // Note: Tests for views requiring @Environment(AppState.self) are in ViewSnapshotTests
    // ViewInspector doesn't fully support the @Observable/@Environment pattern
}

// MARK: - View Content Extraction Tests

@Suite("View Content Extraction Tests")
struct ViewContentExtractionTests {
    @Test("Extract all text from EventRow")
    @MainActor
    func extractAllTextFromEventRow() throws {
        let event = CalendarEventData(
            id: "extract-test",
            title: "Extracted Event Title",
            startDate: Date()
        )

        let view = EventRow(event: event)
        let inspected = try view.inspect()

        let allTexts = inspected.findAll(ViewType.Text.self)
            .compactMap { try? $0.string() }

        // EventRow joins time + title into a single Button label, so check
        // the title appears as a substring of one of the rendered strings.
        #expect(!allTexts.isEmpty)
        #expect(allTexts.contains { $0.contains("Extracted Event Title") })
    }

    @Test("Extract all text from ClubRow")
    @MainActor
    func extractAllTextFromClubRow() throws {
        let club = Club(
            id: 100,
            name: "Extraction Test Club",
            memberCount: 999,
            city: "TestCity",
            sportType: "testing",
            profileMedium: nil
        )
        let syncable = SyncableClub(club: club, isEnabled: true)

        let view = ClubRow(syncableClub: syncable) { _ in }
        let inspected = try view.inspect()

        let allTexts = inspected.findAll(ViewType.Text.self)
            .compactMap { try? $0.string() }

        #expect(allTexts.contains("Extraction Test Club"))
        #expect(allTexts.contains("TestCity"))
        #expect(allTexts.contains { $0.contains("999") })
    }

    // Note: Tests for views requiring @Environment(AppState.self) are covered by ViewSnapshotTests
    // ViewInspector doesn't fully support the @Observable/@Environment pattern
}

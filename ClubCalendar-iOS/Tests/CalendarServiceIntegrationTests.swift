import Testing
import Foundation
import EventKit
import ClubCalendarCore

/// Real-EventKit integration tests for the iOS app.
///
/// These tests touch a live `EKEventStore` running inside the simulator.
/// They require Calendar permission to be pre-granted to the host bundle
/// via:
///
///     xcrun simctl privacy <UDID> grant calendar com.clubcalendar.ios
///
/// `make ios-test` runs this for you. When access isn't granted, the tests
/// politely skip themselves rather than fail — that way `xcodebuild test`
/// on a fresh simulator still reports green.
@MainActor
@Suite("CalendarService — real EventKit")
struct CalendarServiceIntegrationTests {
    /// Use a uniquely-named calendar per test so concurrent runs and reruns
    /// don't fight over the same EKCalendar.
    private static func makeCalendarName() -> String {
        "Club Calendar Test \(Int.random(in: 100_000...999_999))"
    }

    /// Builds two club events that share a club id but have distinct event
    /// ids — exercises the dedup pathway.
    private static func makeFixtureEvents(now: Date) -> [ClubEvent] {
        let clubId = 1001
        let clubName = "Test Cycling Club"
        return [
            ClubEvent(
                id: 9001,
                title: "Morning Ride",
                clubName: clubName,
                clubId: clubId,
                description: "Easy spin",
                activityType: "cycling",
                startDatetime: now.addingTimeInterval(3600),
                address: "Pier 35",
                privateEvent: false,
                organizingAthlete: nil,
                routeId: nil
            ),
            ClubEvent(
                id: 9002,
                title: "Hill Repeats",
                clubName: clubName,
                clubId: clubId,
                description: nil,
                activityType: "cycling",
                startDatetime: now.addingTimeInterval(7200),
                address: nil,
                privateEvent: false,
                organizingAthlete: nil,
                routeId: nil
            ),
        ]
    }

    private func skipIfNoCalendarAccess() async -> Bool {
        let status = EKEventStore.authorizationStatus(for: .event)
        return status != .fullAccess
    }

    @Test func syncEvents_creates_EKEvents_with_strava_id_url() async throws {
        if await skipIfNoCalendarAccess() {
            // Permission not granted by simctl privacy — skip cleanly.
            return
        }

        let calendarName = Self.makeCalendarName()
        let service = CalendarService(calendarName: calendarName)
        defer { Task { @MainActor in await cleanup(calendarName: calendarName) } }

        let events = Self.makeFixtureEvents(now: Date())
        let result = try await service.syncEvents(events)

        #expect(result.created == 2)
        #expect(result.updated == 0)
        #expect(result.cancelled == 0)

        // Verify the EKEvents actually exist in the store with the Strava ID
        // encoded in `url`. We query the store from outside the actor by
        // looking up the calendar by name — EKCalendar isn't Sendable, so
        // we deliberately don't return it from the actor.
        let store = EKEventStore()
        guard let calendar = store.calendars(for: .event).first(where: { $0.title == calendarName }) else {
            Issue.record("Calendar '\(calendarName)' wasn't created")
            return
        }
        let predicate = store.predicateForEvents(
            withStart: Date().addingTimeInterval(-3600),
            end: Date().addingTimeInterval(7200 * 2),
            calendars: [calendar]
        )
        let materialized = store.events(matching: predicate)
        #expect(materialized.count == 2)
        let urlPaths = Set(materialized.compactMap { $0.url?.pathComponents.last })
        #expect(urlPaths == ["9001", "9002"])
    }

    @Test func syncEvents_is_idempotent_no_duplicates_on_resync() async throws {
        if await skipIfNoCalendarAccess() {
            return
        }
        let calendarName = Self.makeCalendarName()
        let service = CalendarService(calendarName: calendarName)
        defer { Task { @MainActor in await cleanup(calendarName: calendarName) } }

        let events = Self.makeFixtureEvents(now: Date())
        _ = try await service.syncEvents(events)
        let second = try await service.syncEvents(events)

        // The second sync should not create new events for the same Strava IDs.
        #expect(second.created == 0)
    }

    @Test func syncEvents_marks_missing_future_events_cancelled() async throws {
        if await skipIfNoCalendarAccess() {
            return
        }
        let calendarName = Self.makeCalendarName()
        let service = CalendarService(calendarName: calendarName)
        defer { Task { @MainActor in await cleanup(calendarName: calendarName) } }

        let events = Self.makeFixtureEvents(now: Date())
        _ = try await service.syncEvents(events)

        // Re-sync with only the first event — the second should be marked
        // [CANCELLED] in the calendar.
        let only = [events[0]]
        let result = try await service.syncEvents(only)
        #expect(result.cancelled == 1)
    }

    @Test func getUpcomingEvents_filters_cancelled_entries() async throws {
        if await skipIfNoCalendarAccess() {
            return
        }
        let calendarName = Self.makeCalendarName()
        let service = CalendarService(calendarName: calendarName)
        defer { Task { @MainActor in await cleanup(calendarName: calendarName) } }

        let events = Self.makeFixtureEvents(now: Date())
        _ = try await service.syncEvents(events)
        // Drop one event to mark it cancelled.
        _ = try await service.syncEvents([events[0]])

        let upcoming = await service.getUpcomingEvents(limit: 10)
        // Only the non-cancelled future event survives.
        #expect(upcoming.contains { $0.title.contains("Morning Ride") })
        #expect(!upcoming.contains { $0.title.hasPrefix("[CANCELLED]") })
    }

    // MARK: - cleanup

    private func cleanup(calendarName: String) async {
        // Best-effort: locate and delete the calendar we created so reruns
        // don't accumulate calendars in the simulator.
        let store = EKEventStore()
        if let cal = store.calendars(for: .event).first(where: { $0.title == calendarName }) {
            try? store.removeCalendar(cal, commit: true)
        }
    }
}

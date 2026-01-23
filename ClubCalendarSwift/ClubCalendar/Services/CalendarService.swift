import Foundation
import EventKit
import AppKit

/// Errors from calendar operations.
enum CalendarError: Error, LocalizedError, Sendable {
    case accessDenied
    case accessRestricted
    case calendarNotFound
    case eventCreationFailed
    case eventUpdateFailed
    case unknownError(Error)

    var errorDescription: String? {
        switch self {
        case .accessDenied:
            return "Calendar access denied. Please grant access in System Settings > Privacy & Security > Calendars."
        case .accessRestricted:
            return "Calendar access is restricted on this device."
        case .calendarNotFound:
            return "Could not find or create the calendar."
        case .eventCreationFailed:
            return "Failed to create calendar event."
        case .eventUpdateFailed:
            return "Failed to update calendar event."
        case .unknownError(let error):
            return "Calendar error: \(error.localizedDescription)"
        }
    }
}

/// Calendar access status.
enum CalendarAccessStatus: Sendable {
    case authorized
    case denied
    case restricted
    case notDetermined
}

/// Manages calendar operations using EventKit.
actor CalendarService {
    private let eventStore: EKEventStore
    private let calendarName: String

    init(calendarName: String = "Club Calendar") {
        self.eventStore = EKEventStore()
        self.calendarName = calendarName
    }

    // MARK: - Access Management

    /// Checks the current calendar access status.
    func checkAccessStatus() -> CalendarAccessStatus {
        let status = EKEventStore.authorizationStatus(for: .event)
        switch status {
        case .fullAccess, .authorized:
            return .authorized
        case .denied:
            return .denied
        case .restricted:
            return .restricted
        case .notDetermined:
            return .notDetermined
        case .writeOnly:
            return .denied  // We need read access too
        @unknown default:
            return .notDetermined
        }
    }

    /// Requests full calendar access.
    func requestAccess() async throws {
        let granted = try await eventStore.requestFullAccessToEvents()
        if !granted {
            throw CalendarError.accessDenied
        }
    }

    // MARK: - Calendar Management

    /// Gets or creates the target calendar.
    func getOrCreateCalendar() throws -> EKCalendar {
        let calendarName = calendarName

        // Look for existing calendar
        let calendars = eventStore.calendars(for: .event)
        if let existing = calendars.first(where: { $0.title == calendarName }) {
            return existing
        }

        // Create new calendar
        let calendar = EKCalendar(for: .event, eventStore: eventStore)
        calendar.title = calendarName

        // Find a local source to use
        let sources = eventStore.sources
        let localSource = sources.first { $0.sourceType == .local }
            ?? sources.first { $0.sourceType == .calDAV }
            ?? sources.first

        guard let source = localSource else {
            throw CalendarError.calendarNotFound
        }

        calendar.source = source

        do {
            try eventStore.saveCalendar(calendar, commit: true)
            return calendar
        } catch {
            throw CalendarError.unknownError(error)
        }
    }

    /// Gets all available calendars.
    func getAvailableCalendars() -> [EKCalendar] {
        eventStore.calendars(for: .event)
            .filter { $0.allowsContentModifications }
            .sorted { $0.title < $1.title }
    }

    /// Gets all available calendar names.
    func getAvailableCalendarNames() -> [String] {
        eventStore.calendars(for: .event)
            .filter { $0.allowsContentModifications }
            .sorted { $0.title < $1.title }
            .map(\.title)
    }

    /// Gets a calendar by name.
    func getCalendar(named name: String) -> EKCalendar? {
        eventStore.calendars(for: .event).first { $0.title == name }
    }

    // MARK: - Event Sync

    /// Syncs Strava events to the calendar.
    func syncEvents(_ clubEvents: [ClubEvent]) async throws -> SyncResult {
        let calendar = try getOrCreateCalendar()
        var created = 0
        var updated = 0
        var cancelled = 0

        // Get existing events from the calendar (next 90 days)
        let startDate = Date()
        let endDate = Calendar.current.date(byAdding: .day, value: 90, to: startDate)!
        let predicate = eventStore.predicateForEvents(
            withStart: startDate,
            end: endDate,
            calendars: [calendar]
        )
        let existingEvents = eventStore.events(matching: predicate)

        // Build lookup of existing events by Strava ID (stored in URL)
        var existingByStravaId: [Int: EKEvent] = [:]
        for event in existingEvents {
            if let url = event.url,
               let stravaId = extractStravaId(from: url) {
                existingByStravaId[stravaId] = event
            }
        }

        // Track which Strava events are still active
        let activeStravaIds = Set(clubEvents.map(\.id))

        // Process each Strava event
        for clubEvent in clubEvents {
            if let existingEvent = existingByStravaId[clubEvent.id] {
                // Update existing event if changed
                if updateEvent(existingEvent, from: clubEvent) {
                    do {
                        try eventStore.save(existingEvent, span: .thisEvent)
                        updated += 1
                    } catch {
                        print("Failed to update event: \(error)")
                    }
                }
            } else {
                // Create new event
                let event = EKEvent(eventStore: eventStore)
                configureEvent(event, from: clubEvent, calendar: calendar)
                do {
                    try eventStore.save(event, span: .thisEvent)
                    created += 1
                } catch {
                    print("Failed to create event: \(error)")
                }
            }
        }

        // Mark events as cancelled if they're no longer in Strava
        for (stravaId, existingEvent) in existingByStravaId {
            if !activeStravaIds.contains(stravaId) {
                // Event was removed from Strava - mark as cancelled
                if !existingEvent.title.hasPrefix("[CANCELLED]") {
                    existingEvent.title = "[CANCELLED] \(existingEvent.title ?? "")"
                    do {
                        try eventStore.save(existingEvent, span: .thisEvent)
                        cancelled += 1
                    } catch {
                        print("Failed to mark event as cancelled: \(error)")
                    }
                }
            }
        }

        return SyncResult(created: created, updated: updated, cancelled: cancelled)
    }

    // MARK: - Event Helpers

    private func configureEvent(_ event: EKEvent, from clubEvent: ClubEvent, calendar: EKCalendar) {
        event.title = clubEvent.formattedTitle
        event.startDate = clubEvent.startDatetime
        event.endDate = clubEvent.startDatetime.addingTimeInterval(3600)  // 1 hour default
        event.calendar = calendar
        event.url = clubEvent.stravaURL
        event.location = clubEvent.address
        event.notes = buildEventNotes(from: clubEvent)
    }

    /// Updates an existing event, returning true if changes were made.
    private func updateEvent(_ event: EKEvent, from clubEvent: ClubEvent) -> Bool {
        var changed = false

        let newTitle = clubEvent.formattedTitle
        if event.title != newTitle {
            event.title = newTitle
            changed = true
        }

        if event.startDate != clubEvent.startDatetime {
            event.startDate = clubEvent.startDatetime
            event.endDate = clubEvent.startDatetime.addingTimeInterval(3600)
            changed = true
        }

        if event.location != clubEvent.address {
            event.location = clubEvent.address
            changed = true
        }

        return changed
    }

    private func buildEventNotes(from clubEvent: ClubEvent) -> String {
        var notes = [String]()

        if let description = clubEvent.description, !description.isEmpty {
            notes.append(description)
        }

        if let organizer = clubEvent.organizingAthlete {
            notes.append("Organizer: \(organizer.fullName)")
        }

        if let url = clubEvent.stravaURL {
            notes.append("View on Strava: \(url.absoluteString)")
        }

        return notes.joined(separator: "\n\n")
    }

    private func extractStravaId(from url: URL) -> Int? {
        // URL format: https://www.strava.com/clubs/events/123
        let path = url.pathComponents
        guard path.count >= 4,
              path[path.count - 2] == "events",
              let id = Int(path.last ?? "") else {
            return nil
        }
        return id
    }

    // MARK: - Upcoming Events

    /// Gets upcoming events from the calendar as Sendable calendar event data.
    func getUpcomingEvents(limit: Int = 15) -> [CalendarEventData] {
        guard let calendar = getCalendar(named: calendarName) else {
            return []
        }

        let startDate = Date()
        let endDate = Calendar.current.date(byAdding: .day, value: 30, to: startDate)!

        let predicate = eventStore.predicateForEvents(
            withStart: startDate,
            end: endDate,
            calendars: [calendar]
        )

        return eventStore.events(matching: predicate)
            .filter { !$0.title.hasPrefix("[CANCELLED]") }
            .prefix(limit)
            .map { CalendarEventData(from: $0) }
    }
}

// MARK: - Calendar Event Data

/// Sendable representation of a calendar event.
struct CalendarEventData: Identifiable, Sendable {
    let id: String
    let title: String
    let startDate: Date

    init(id: String, title: String, startDate: Date) {
        self.id = id
        self.title = title
        self.startDate = startDate
    }

    init(from event: EKEvent) {
        self.id = event.eventIdentifier ?? UUID().uuidString
        self.title = event.title ?? "Untitled"
        self.startDate = event.startDate
    }
}

// MARK: - Sync Result

struct SyncResult: Sendable {
    let created: Int
    let updated: Int
    let cancelled: Int

    var totalChanges: Int { created + updated + cancelled }
    var hasChanges: Bool { totalChanges > 0 }

    var summary: String {
        if !hasChanges {
            return "No changes"
        }
        var parts: [String] = []
        if created > 0 { parts.append("\(created) created") }
        if updated > 0 { parts.append("\(updated) updated") }
        if cancelled > 0 { parts.append("\(cancelled) cancelled") }
        return parts.joined(separator: ", ")
    }
}

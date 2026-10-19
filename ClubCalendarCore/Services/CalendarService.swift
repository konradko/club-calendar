import Foundation
import EventKit
import os

/// Errors from calendar operations.
public enum CalendarError: Error, LocalizedError, Sendable {
    case accessDenied
    case accessRestricted
    case calendarNotFound
    case eventCreationFailed
    case eventUpdateFailed
    case unknownError(Error)

    public var errorDescription: String? {
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
public enum CalendarAccessStatus: Sendable {
    case authorized
    case denied
    case restricted
    case notDetermined
}

/// Manages calendar operations using EventKit.
public actor CalendarService {
    /// How far around `now` to scan when deduplicating existing events.
    /// Strava only returns upcoming events, so we need a generous lookback
    /// to find past EKEvents that share a Strava ID with a recurring series.
    private static let dedupWindow: TimeInterval = 180 * 24 * 60 * 60

    /// Default duration when Strava doesn't return an end time.
    private static let defaultEventDuration: TimeInterval = 60 * 60

    /// Window for upcoming events shown in the menu bar.
    private static let upcomingEventsWindow: TimeInterval = 30 * 24 * 60 * 60

    /// Title prefix marking events that disappeared from Strava.
    private static let cancelledPrefix = "[CANCELLED]"

    /// EKEventStore persists dates with whole-second precision, so a stored
    /// start date can differ from the source by a fraction of a second.
    /// Treat differences below this as equal or every sync would rewrite
    /// every event whose source date has sub-second precision.
    private static let startDateTolerance: TimeInterval = 1

    private let eventStore: EKEventStore
    private var calendarName: String

    public init(calendarName: String = "Club Calendar") {
        self.eventStore = EKEventStore()
        self.calendarName = calendarName
    }

    /// Points future syncs and lookups at a different calendar. Call when the
    /// user changes the target calendar in settings: the service is created
    /// once at launch, so the initializer's name would otherwise go stale.
    public func setCalendarName(_ name: String) {
        calendarName = name
    }

    // MARK: - Access Management

    /// Checks the current calendar access status.
    public func checkAccessStatus() -> CalendarAccessStatus {
        let status = EKEventStore.authorizationStatus(for: .event)
        let result: CalendarAccessStatus
        switch status {
        case .fullAccess:
            result = .authorized
        case .denied:
            result = .denied
        case .restricted:
            result = .restricted
        case .notDetermined:
            result = .notDetermined
        case .writeOnly:
            // We need read access too — treat write-only as denied so the UI
            // prompts the user to upgrade to full access.
            result = .denied
        @unknown default:
            result = .notDetermined
        }
        Logger.calendar.debug("Calendar access status: \(String(describing: result))")
        return result
    }

    /// Requests full calendar access.
    public func requestAccess() async throws {
        let granted = try await eventStore.requestFullAccessToEvents()
        if !granted {
            throw CalendarError.accessDenied
        }
    }

    // MARK: - Calendar Management

    /// Gets or creates the target calendar.
    public func getOrCreateCalendar() throws -> EKCalendar {
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
    public func getAvailableCalendars() -> [EKCalendar] {
        eventStore.calendars(for: .event)
            .filter { $0.allowsContentModifications }
            .sorted { $0.title < $1.title }
    }

    /// Gets all available calendar names.
    public func getAvailableCalendarNames() -> [String] {
        getAvailableCalendars().map(\.title)
    }

    /// Gets a calendar by name.
    public func getCalendar(named name: String) -> EKCalendar? {
        eventStore.calendars(for: .event).first { $0.title == name }
    }

    // MARK: - Event Sync

    /// Syncs Strava events to the calendar.
    ///
    /// Future calendar events missing from `clubEvents` are marked cancelled,
    /// except events of clubs in `failedClubIds`: their fetch failed, so
    /// their absence says nothing about the event. Events whose club cannot
    /// be read from the stored URL are also left alone while any club failed.
    public func syncEvents(_ clubEvents: [ClubEvent], failedClubIds: Set<Int> = []) async throws -> SyncResult {
        Logger.calendar.info("Syncing \(clubEvents.count) event(s) to calendar")
        let calendar = try getOrCreateCalendar()
        var created = 0
        var updated = 0
        var cancelled = 0

        // Look at a wide window so past EKEvents with the same Strava ID
        // are visible to dedup — the old "now → +90d" predicate missed them
        // and caused a fresh duplicate every time a recurring event rolled
        // over to its next occurrence.
        let now = Date()
        let predicate = eventStore.predicateForEvents(
            withStart: now.addingTimeInterval(-Self.dedupWindow),
            end: now.addingTimeInterval(Self.dedupWindow),
            calendars: [calendar]
        )
        var existingEvents = eventStore.events(matching: predicate)

        // Self-healing: collapse pre-existing duplicates created by older
        // buggy syncs, keeping one event per Strava ID.
        let removedDups = removeDuplicates(in: &existingEvents)
        if removedDups > 0 {
            Logger.calendar.info("Removed \(removedDups) duplicate event(s)")
        }

        // Build lookup of existing events by Strava ID (stored in URL)
        var existingByStravaId: [Int: EKEvent] = [:]
        var clubIdByStravaId: [Int: Int] = [:]
        for event in existingEvents {
            if let url = event.url,
               let ref = parseStravaEventURL(url) {
                existingByStravaId[ref.eventId] = event
                clubIdByStravaId[ref.eventId] = ref.clubId
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
                        Logger.calendar.error("Failed to update event \(clubEvent.id): \(error.localizedDescription)")
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
                    Logger.calendar.error("Failed to create event \(clubEvent.id): \(error.localizedDescription)")
                }
            }
        }

        // Mark future events as cancelled if they're no longer in Strava.
        // Past events stay untouched — Strava only returns upcoming events, so
        // their absence from `activeStravaIds` doesn't mean they were cancelled.
        var skippedForFailedClubs = 0
        for (stravaId, existingEvent) in existingByStravaId {
            guard existingEvent.startDate >= now else { continue }
            if !activeStravaIds.contains(stravaId) {
                let clubFetchSucceeded = clubIdByStravaId[stravaId].map { !failedClubIds.contains($0) } ?? false
                if !failedClubIds.isEmpty, !clubFetchSucceeded {
                    skippedForFailedClubs += 1
                    continue
                }
                // `title` is implicitly-unwrapped and can be nil for events the
                // user hollowed out by hand, so avoid the force-unwrap.
                if existingEvent.title?.hasPrefix(Self.cancelledPrefix) != true {
                    existingEvent.title = "\(Self.cancelledPrefix) \(existingEvent.title ?? "")"
                    do {
                        try eventStore.save(existingEvent, span: .thisEvent)
                        cancelled += 1
                    } catch {
                        Logger.calendar.error("Failed to cancel event \(stravaId): \(error.localizedDescription)")
                    }
                }
            }
        }

        if skippedForFailedClubs > 0 {
            Logger.calendar.warning("Left \(skippedForFailedClubs) event(s) unchanged: their club fetch failed")
        }

        let result = SyncResult(created: created, updated: updated, cancelled: cancelled)
        Logger.calendar.info("Calendar sync result: \(result.summary)")
        return result
    }

    // MARK: - Event Helpers

    private func configureEvent(_ event: EKEvent, from clubEvent: ClubEvent, calendar: EKCalendar) {
        event.title = clubEvent.formattedTitle
        event.startDate = clubEvent.startDatetime
        event.endDate = clubEvent.startDatetime.addingTimeInterval(Self.defaultEventDuration)
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

        let startUnchanged = event.startDate
            .map { abs($0.timeIntervalSince(clubEvent.startDatetime)) < Self.startDateTolerance }
            ?? false
        if !startUnchanged {
            event.startDate = clubEvent.startDatetime
            event.endDate = clubEvent.startDatetime.addingTimeInterval(Self.defaultEventDuration)
            changed = true
        }

        if event.location != clubEvent.address {
            event.location = clubEvent.address
            changed = true
        }

        // EKEvent normalizes empty notes to nil, so coalesce before comparing
        // or unchanged events would report as updated on every sync.
        let newNotes = buildEventNotes(from: clubEvent)
        if (event.notes ?? "") != newNotes {
            event.notes = newNotes
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

    /// Collapses duplicate EKEvents that share a Strava ID. Mutates `events`
    /// in place to drop the removed entries, returns the count removed.
    /// Keeps one event per Strava ID, preferring the future occurrence
    /// closest to `Date()` so the surviving entry represents the live event.
    private func removeDuplicates(in events: inout [EKEvent]) -> Int {
        var groups: [Int: [EKEvent]] = [:]
        var unkeyed: [EKEvent] = []
        for event in events {
            if let url = event.url, let stravaId = extractStravaId(from: url) {
                groups[stravaId, default: []].append(event)
            } else {
                unkeyed.append(event)
            }
        }

        let now = Date()
        var keepers: [EKEvent] = unkeyed
        var removed = 0

        for (_, group) in groups {
            guard group.count > 1 else {
                keepers.append(contentsOf: group)
                continue
            }
            let sorted = group.sorted { lhs, rhs in
                let lhsFuture = lhs.startDate >= now
                let rhsFuture = rhs.startDate >= now
                if lhsFuture != rhsFuture {
                    return lhsFuture  // future ones first
                }
                if lhsFuture {
                    return lhs.startDate < rhs.startDate  // soonest future
                }
                return lhs.startDate > rhs.startDate  // most recent past
            }
            let keeper = sorted.first!
            keepers.append(keeper)
            for victim in sorted.dropFirst() {
                do {
                    try eventStore.remove(victim, span: .thisEvent)
                    removed += 1
                } catch {
                    Logger.calendar.error("Failed to remove duplicate: \(error.localizedDescription)")
                    keepers.append(victim)
                }
            }
        }

        events = keepers
        return removed
    }

    private func extractStravaId(from url: URL) -> Int? {
        parseStravaEventURL(url)?.eventId
    }

    /// Reads the Strava event ID, and the club ID when present, from an event URL.
    /// Accepts both the real format (clubs/{club_id}/group_events/{event_id})
    /// and the legacy Swift-app format (clubs/events/{event_id}) so events
    /// created by older builds are still recognized for dedup. Legacy URLs
    /// carry no club ID.
    private func parseStravaEventURL(_ url: URL) -> (clubId: Int?, eventId: Int)? {
        let path = url.pathComponents
        guard path.count >= 4,
              let eventId = Int(path.last ?? "") else {
            return nil
        }
        let parent = path[path.count - 2]
        switch parent {
        case "group_events":
            return (clubId: Int(path[path.count - 3]), eventId: eventId)
        case "events":
            return (clubId: nil, eventId: eventId)
        default:
            return nil
        }
    }

    // MARK: - Upcoming Events

    /// Gets upcoming events from the calendar as Sendable calendar event data.
    public func getUpcomingEvents(limit: Int = 15) -> [CalendarEventData] {
        guard let calendar = getCalendar(named: calendarName) else {
            return []
        }

        let startDate = Date()
        let endDate = startDate.addingTimeInterval(Self.upcomingEventsWindow)

        let predicate = eventStore.predicateForEvents(
            withStart: startDate,
            end: endDate,
            calendars: [calendar]
        )

        // `events(matching:)` returns results in no particular order, so sort
        // before taking `limit` to keep the soonest events, not arbitrary ones.
        return eventStore.events(matching: predicate)
            .filter { $0.title?.hasPrefix(Self.cancelledPrefix) != true }
            .sorted { $0.startDate < $1.startDate }
            .prefix(limit)
            .map { CalendarEventData(from: $0) }
    }
}

// MARK: - Calendar Event Data

/// Sendable representation of a calendar event.
public struct CalendarEventData: Identifiable, Sendable {
    public let id: String
    public let title: String
    public let startDate: Date
    public let url: URL?

    public init(id: String, title: String, startDate: Date, url: URL? = nil) {
        self.id = id
        self.title = title
        self.startDate = startDate
        self.url = url
    }

    public init(from event: EKEvent) {
        self.id = event.eventIdentifier ?? UUID().uuidString
        self.title = event.title ?? "Untitled"
        self.startDate = event.startDate
        self.url = event.url
    }
}

// MARK: - Sync Result

public struct SyncResult: Sendable {
    public let created: Int
    public let updated: Int
    public let cancelled: Int

    public init(created: Int, updated: Int, cancelled: Int) {
        self.created = created
        self.updated = updated
        self.cancelled = cancelled
    }

    public var totalChanges: Int { created + updated + cancelled }
    public var hasChanges: Bool { totalChanges > 0 }

    public var summary: String {
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

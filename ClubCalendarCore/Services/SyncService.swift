import Foundation
import Combine
import os
#if canImport(AppKit)
import AppKit
#endif

extension Notification.Name {
    /// Posted on the main queue after a successful `SyncService.sync()` so
    /// derived UI state (e.g. AppState's cached upcoming events) can refresh.
    public static let syncDidComplete = Notification.Name("ClubCalendar.SyncService.syncDidComplete")
}

/// Orchestrates syncing between Strava and Calendar.
///
/// The core `sync()` / `syncIfStale()` / `refreshClubs()` logic is platform-
/// agnostic. Periodic auto-sync scheduling is macOS-only (via
/// `NSBackgroundActivityScheduler`); on iOS the host app registers a
/// `BGAppRefreshTask` and calls `sync()` directly from the handler.
@MainActor
@Observable
public final class SyncService {
    private let stravaService: StravaService
    private let calendarService: CalendarService
    private let settings: AppSettings
    #if canImport(AppKit)
    private var scheduler: NSBackgroundActivityScheduler?
    private var wakeObserver: NSObjectProtocol?
    #endif
    private var isSyncing = false

    public var lastSyncTime: Date?
    public var lastSyncResult: SyncResult?
    public var lastSyncError: Error?
    public var syncInProgress: Bool { isSyncing }

    public init(
        stravaService: StravaService,
        calendarService: CalendarService,
        settings: AppSettings = .shared
    ) {
        self.stravaService = stravaService
        self.calendarService = calendarService
        self.settings = settings
    }

    // MARK: - Scheduler Management (macOS only)

    #if canImport(AppKit)
    /// Starts the auto-sync scheduler based on settings. Idempotent — calling
    /// while already running is a no-op (use `restartAutoSync()` after a
    /// settings change to pick up a new interval).
    public func startAutoSync() {
        guard scheduler == nil else { return }

        let interval = settings.syncInterval
        guard interval != .never else { return }

        // NSBackgroundActivityScheduler is Apple's recommended API for
        // periodic work on macOS: it isn't throttled by App Nap, batches with
        // other system activities, and resumes scheduling automatically after
        // wake. Foundation timers (even with .common / beginActivity) drift
        // or stop on long-idle LSUIElement apps.
        let activity = NSBackgroundActivityScheduler(
            identifier: "com.clubcalendar.app.sync"
        )
        activity.repeats = true
        activity.interval = TimeInterval(interval.rawValue * 60)
        // 10% tolerance lets the system coalesce our wakeups with others.
        activity.tolerance = TimeInterval(interval.rawValue * 60) / 10
        activity.qualityOfService = .utility
        activity.schedule { [weak self] completion in
            Task { @MainActor [weak self] in
                await self?.sync()
                completion(.finished)
            }
        }
        scheduler = activity

        // The scheduler is paused while the Mac sleeps and the next fire may
        // be up to one interval after wake. Force an immediate catch-up on
        // wake so a 60-minute interval doesn't mean a 60-minute stale menu.
        wakeObserver = NSWorkspace.shared.notificationCenter.addObserver(
            forName: NSWorkspace.didWakeNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor [weak self] in
                Logger.sync.info("System woke — triggering sync")
                await self?.sync()
            }
        }

        // Run initial sync
        Task {
            await sync()
        }
    }

    /// Stops the auto-sync scheduler.
    public func stopAutoSync() {
        scheduler?.invalidate()
        scheduler = nil
        if let observer = wakeObserver {
            NSWorkspace.shared.notificationCenter.removeObserver(observer)
            wakeObserver = nil
        }
    }

    /// Restarts auto-sync (call when settings change).
    public func restartAutoSync() {
        stopAutoSync()
        startAutoSync()
    }
    #endif

    /// Triggers a sync if the last successful sync is older than the configured
    /// interval. Called when the menu opens so the user sees fresh data even
    /// if the scheduler hasn't fired yet (e.g. just after wake).
    public func syncIfStale() async {
        let interval = settings.syncInterval
        guard interval != .never else { return }
        let intervalSeconds = TimeInterval(interval.rawValue * 60)

        if let last = lastSyncTime, Date().timeIntervalSince(last) < intervalSeconds {
            return
        }
        await sync()
    }

    // MARK: - Sync Operations

    /// Performs a full sync of all enabled clubs.
    public func sync() async {
        // Prevent concurrent syncs
        guard !isSyncing else {
            Logger.sync.debug("Sync already in progress, skipping")
            return
        }
        isSyncing = true
        defer { isSyncing = false }

        Logger.sync.info("Starting sync...")
        lastSyncError = nil

        do {
            // Check calendar access
            let accessStatus = await calendarService.checkAccessStatus()
            guard accessStatus == .authorized else {
                Logger.sync.error("Calendar access not authorized")
                throw CalendarError.accessDenied
            }

            // Get enabled club IDs
            let clubIds = Array(settings.enabledClubIds)
            guard !clubIds.isEmpty else {
                Logger.sync.info("No clubs enabled, nothing to sync")
                lastSyncResult = SyncResult(created: 0, updated: 0, cancelled: 0)
                lastSyncTime = Date()
                return
            }

            Logger.sync.info("Fetching events for \(clubIds.count) club(s)")

            // Fetch events from Strava
            let events = await stravaService.getEventsForClubs(clubIds)
            Logger.sync.info("Fetched \(events.count) event(s) from Strava")

            // Sync to calendar
            let result = try await calendarService.syncEvents(events)

            Logger.sync.info("Sync complete: \(result.summary)")
            lastSyncResult = result
            lastSyncTime = Date()
            NotificationCenter.default.post(name: .syncDidComplete, object: nil)
        } catch {
            lastSyncError = error
            Logger.sync.error("Sync failed: \(error.localizedDescription)")
        }
    }

    /// Fetches clubs from Strava and updates settings.
    public func refreshClubs() async throws {
        Logger.sync.info("Refreshing clubs from Strava")
        let clubs = try await stravaService.getAthleteClubs()
        Logger.sync.info("Fetched \(clubs.count) club(s)")
        settings.updateClubs(clubs)
    }

    // MARK: - Formatted Status

    /// Formatted string for last sync time.
    public var lastSyncTimeFormatted: String? {
        guard let time = lastSyncTime else { return nil }
        if Calendar.current.isDateInToday(time) {
            return time.formatted(date: .omitted, time: .shortened)
        }
        return time.formatted(date: .numeric, time: .shortened)
    }
}

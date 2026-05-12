import Foundation
import Combine
import AppKit
import os

/// Orchestrates syncing between Strava and Calendar.
@MainActor
@Observable
final class SyncService {
    private let stravaService: StravaService
    private let calendarService: CalendarService
    private let settings: AppSettings
    private var syncTimer: Timer?
    private var wakeObserver: NSObjectProtocol?
    private var activityToken: NSObjectProtocol?
    private var isSyncing = false

    var lastSyncTime: Date?
    var lastSyncResult: SyncResult?
    var lastSyncError: Error?
    var syncInProgress: Bool { isSyncing }

    init(
        stravaService: StravaService,
        calendarService: CalendarService,
        settings: AppSettings = .shared
    ) {
        self.stravaService = stravaService
        self.calendarService = calendarService
        self.settings = settings
    }

    // MARK: - Timer Management

    /// Starts the auto-sync timer based on settings.
    func startAutoSync() {
        stopAutoSync()

        let interval = settings.syncInterval
        guard interval != .never else { return }

        // App Nap throttles Foundation timers on idle LSUIElement apps, so a
        // menu bar app left untouched for hours stops firing its sync timer.
        // Holding a user-initiated activity tells macOS we're doing periodic
        // work that must run on schedule (system sleep is still allowed).
        activityToken = ProcessInfo.processInfo.beginActivity(
            options: [.userInitiatedAllowingIdleSystemSleep],
            reason: "Club Calendar periodic Strava sync"
        )

        let intervalSeconds = TimeInterval(interval.rawValue * 60)
        let timer = Timer(timeInterval: intervalSeconds, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                await self?.sync()
            }
        }
        // .common keeps the timer firing while menus / modal panels are open
        // (those run loop modes would otherwise pause a .default-mode timer).
        RunLoop.main.add(timer, forMode: .common)
        syncTimer = timer

        // Foundation timers don't fire while the Mac is asleep; without this
        // hook the app can sit idle for days after a wake. Trigger a sync as
        // soon as the system reports it has woken up.
        wakeObserver = NSWorkspace.shared.notificationCenter.addObserver(
            forName: NSWorkspace.didWakeNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor [weak self] in
                Logger.sync.info("System woke — triggering sync")
                FileLog.write("System woke — triggering sync", category: "sync")
                await self?.sync()
            }
        }

        // Run initial sync
        Task {
            await sync()
        }
    }

    /// Stops the auto-sync timer.
    func stopAutoSync() {
        syncTimer?.invalidate()
        syncTimer = nil
        if let observer = wakeObserver {
            NSWorkspace.shared.notificationCenter.removeObserver(observer)
            wakeObserver = nil
        }
        if let token = activityToken {
            ProcessInfo.processInfo.endActivity(token)
            activityToken = nil
        }
    }

    /// Restarts auto-sync (call when settings change).
    func restartAutoSync() {
        startAutoSync()
    }

    // MARK: - Sync Operations

    /// Performs a full sync of all enabled clubs.
    func sync() async {
        // Prevent concurrent syncs
        guard !isSyncing else {
            Logger.sync.debug("Sync already in progress, skipping")
            return
        }
        isSyncing = true
        defer { isSyncing = false }

        Logger.sync.info("Starting sync...")
        FileLog.write("Starting sync...", category: "sync")
        lastSyncError = nil

        do {
            // Check calendar access
            let accessStatus = await calendarService.checkAccessStatus()
            guard accessStatus == .authorized else {
                Logger.sync.error("Calendar access not authorized")
                FileLog.write("Calendar access not authorized", level: "ERROR", category: "sync")
                throw CalendarError.accessDenied
            }

            // Get enabled club IDs
            let clubIds = Array(settings.enabledClubIds)
            guard !clubIds.isEmpty else {
                Logger.sync.info("No clubs enabled, nothing to sync")
                FileLog.write("No clubs enabled, nothing to sync", category: "sync")
                lastSyncResult = SyncResult(created: 0, updated: 0, cancelled: 0)
                lastSyncTime = Date()
                return
            }

            Logger.sync.info("Fetching events for \(clubIds.count) club(s)")
            FileLog.write("Fetching events for \(clubIds.count) club(s): \(clubIds)", category: "sync")

            // Fetch events from Strava
            let events = try await stravaService.getEventsForClubs(clubIds)
            Logger.sync.info("Fetched \(events.count) event(s) from Strava")
            FileLog.write("Fetched \(events.count) event(s) from Strava", category: "sync")

            // Sync to calendar
            let result = try await calendarService.syncEvents(events)

            Logger.sync.info("Sync complete: \(result.summary)")
            FileLog.write("Sync complete: \(result.summary)", category: "sync")
            lastSyncResult = result
            lastSyncTime = Date()
        } catch {
            lastSyncError = error
            Logger.sync.error("Sync failed: \(error.localizedDescription)")
            FileLog.write("Sync failed: \(error.localizedDescription)", level: "ERROR", category: "sync")
        }
    }

    /// Fetches clubs from Strava and updates settings.
    func refreshClubs() async throws {
        Logger.sync.info("Refreshing clubs from Strava")
        FileLog.write("Refreshing clubs from Strava", category: "sync")
        let clubs = try await stravaService.getAthleteClubs()
        Logger.sync.info("Fetched \(clubs.count) club(s)")
        FileLog.write("Fetched \(clubs.count) club(s)", category: "sync")
        settings.updateClubs(clubs)
    }

    // MARK: - Formatted Status

    /// Formatted string for last sync time.
    var lastSyncTimeFormatted: String? {
        guard let time = lastSyncTime else { return nil }

        let formatter = DateFormatter()
        if Calendar.current.isDateInToday(time) {
            formatter.timeStyle = .short
            formatter.dateStyle = .none
        } else {
            formatter.timeStyle = .short
            formatter.dateStyle = .short
        }
        return formatter.string(from: time)
    }
}

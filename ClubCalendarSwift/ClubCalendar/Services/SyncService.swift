import Foundation
import Combine

/// Orchestrates syncing between Strava and Calendar.
@MainActor
@Observable
final class SyncService {
    private let stravaService: StravaService
    private let calendarService: CalendarService
    private let settings: AppSettings
    private var syncTimer: Timer?
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

        let intervalSeconds = TimeInterval(interval.rawValue * 60)
        syncTimer = Timer.scheduledTimer(withTimeInterval: intervalSeconds, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
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
    }

    /// Restarts auto-sync (call when settings change).
    func restartAutoSync() {
        startAutoSync()
    }

    // MARK: - Sync Operations

    /// Performs a full sync of all enabled clubs.
    func sync() async {
        // Prevent concurrent syncs
        guard !isSyncing else { return }
        isSyncing = true
        defer { isSyncing = false }

        lastSyncError = nil

        do {
            // Check calendar access
            let accessStatus = await calendarService.checkAccessStatus()
            guard accessStatus == .authorized else {
                throw CalendarError.accessDenied
            }

            // Get enabled club IDs
            let clubIds = Array(settings.enabledClubIds)
            guard !clubIds.isEmpty else {
                lastSyncResult = SyncResult(created: 0, updated: 0, cancelled: 0)
                lastSyncTime = Date()
                return
            }

            // Fetch events from Strava
            let events = try await stravaService.getEventsForClubs(clubIds)

            // Sync to calendar
            let result = try await calendarService.syncEvents(events)

            lastSyncResult = result
            lastSyncTime = Date()
        } catch {
            lastSyncError = error
            print("Sync failed: \(error)")
        }
    }

    /// Fetches clubs from Strava and updates settings.
    func refreshClubs() async throws {
        let clubs = try await stravaService.getAthleteClubs()
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

import Foundation
import BackgroundTasks
import os
import ClubCalendarCore

/// Wires BGAppRefreshTask into the shared SyncService.
///
/// iOS won't honor a fixed cadence — `setTaskRequest` is a hint, not a
/// guarantee. We request the user's chosen interval as `earliestBeginDate`,
/// but the system may delay (or skip) us based on usage patterns. The
/// scenePhase-driven foreground sync in AppState picks up whatever the
/// background path misses.
enum BackgroundSyncCoordinator {
    static let taskIdentifier = "com.clubcalendar.sync"

    private nonisolated(unsafe) static var syncService: SyncService?
    private nonisolated(unsafe) static var settings: AppSettings?
    /// `BGTaskScheduler.register` throws (NSException → SIGABRT) when called
    /// twice in the same process. This guard makes the call idempotent so the
    /// test host can construct `ClubCalendarApp()` more than once without
    /// crashing the test runner.
    private nonisolated(unsafe) static var didRegister = false

    /// Registers the BGTask handler. Must be called before the app finishes
    /// launching (before the first scene activates). Idempotent — second
    /// call is a no-op.
    static func register() {
        guard !didRegister else { return }
        didRegister = true
        BGTaskScheduler.shared.register(
            forTaskWithIdentifier: taskIdentifier,
            using: nil
        ) { task in
            guard let refresh = task as? BGAppRefreshTask else {
                task.setTaskCompleted(success: false)
                return
            }
            handle(task: refresh)
        }
    }

    /// Wires the live SyncService + AppSettings instances so the handler
    /// can drive them when the system delivers a refresh.
    @MainActor
    static func configure(syncService: SyncService, settings: AppSettings) {
        Self.syncService = syncService
        Self.settings = settings
    }

    /// Requests another background refresh, scheduled at the user's chosen
    /// interval from now. Called after each background run completes, and
    /// whenever the app moves to the background.
    @MainActor
    static func scheduleNextRun() {
        guard let settings, settings.syncInterval != .never else {
            Logger.sync.debug("Auto-sync disabled, not scheduling background task")
            return
        }

        let request = BGAppRefreshTaskRequest(identifier: taskIdentifier)
        request.earliestBeginDate = Date().addingTimeInterval(
            TimeInterval(settings.syncInterval.rawValue * 60)
        )

        do {
            try BGTaskScheduler.shared.submit(request)
            Logger.sync.info("Scheduled next background sync at \(request.earliestBeginDate?.description ?? "<unknown>", privacy: .public)")
        } catch {
            Logger.sync.error("Failed to schedule background sync: \(error.localizedDescription, privacy: .public)")
        }
    }

    private static func handle(task: BGAppRefreshTask) {
        Logger.sync.info("Background sync task fired")

        // Reschedule first — if the sync hangs, we still get another shot.
        Task { @MainActor in scheduleNextRun() }

        let work = Task { @MainActor in
            await performScheduledSync()
        }

        // BGAppRefreshTask isn't Sendable, but BGTaskScheduler hands it back
        // to us on a single thread and never touches it again once we call
        // setTaskCompleted. Use `nonisolated(unsafe)` to acknowledge that
        // capture across the Task boundary is safe in this specific flow.
        nonisolated(unsafe) let unsafeTask = task

        task.expirationHandler = {
            Logger.sync.error("Background sync task expired before completion")
            work.cancel()
        }

        Task {
            let success = await work.value
            unsafeTask.setTaskCompleted(success: success)
        }
    }

    /// Runs the configured sync and reports whether it ended without error.
    /// Exposed for tests; production callers go through `handle(task:)`.
    @MainActor
    static func performScheduledSync() async -> Bool {
        await syncService?.sync()
        return syncService?.lastSyncError == nil
    }

    #if DEBUG
    /// Resets the static service references. Test-only — keeps suites
    /// independent of any other test's `configure()` call.
    @MainActor
    static func _resetForTesting() {
        syncService = nil
        settings = nil
    }
    #endif
}

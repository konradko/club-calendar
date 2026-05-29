import Foundation
import SwiftUI
import EventKit
import os
import ClubCalendarCore

/// Type alias for clarity at call sites.
typealias UpcomingEvent = CalendarEventData

/// iOS composition root + observable UI state. Mirrors the macOS AppState
/// but drops menu-bar, login-item, and wake-notification plumbing in favor
/// of scenePhase-driven refresh.
@MainActor
@Observable
final class AppState {
    let stravaService: StravaService
    let calendarService: CalendarService
    let authService: AuthService
    let syncService: SyncService
    let settings: AppSettings
    private let keychain: any KeychainHelperProtocol
    private var syncCompleteObserver: NSObjectProtocol?

    // UI state
    var showOnboarding = false
    var calendarAccessStatus: CalendarAccessStatus = .notDetermined
    var upcomingEvents: [UpcomingEvent] = []
    var availableCalendarNames: [String] = []
    var isLoading = false
    var errorMessage: String?

    // Auth state
    var isAuthenticated = false
    var athleteName: String?
    var hasAPICredentials = false

    /// Production initializer — wires real shared singletons.
    convenience init() {
        self.init(keychain: KeychainHelper.shared, settings: AppSettings.shared)
    }

    /// Designated initializer. Tests pass a `MockKeychainHelper` and an
    /// optional `CalendarService` so they can run without touching the
    /// real keychain (which requires signing on iOS).
    init(
        keychain: any KeychainHelperProtocol,
        settings: AppSettings,
        calendarService: CalendarService? = nil
    ) {
        let stravaService = StravaService(keychain: keychain)
        let calendarService = calendarService ?? CalendarService(calendarName: settings.calendarName)

        self.keychain = keychain
        self.settings = settings
        self.stravaService = stravaService
        self.calendarService = calendarService
        self.authService = AuthService(keychain: keychain, stravaService: stravaService)
        self.syncService = SyncService(
            stravaService: stravaService,
            calendarService: calendarService,
            settings: settings
        )

        // Background-task syncs bypass `AppState.sync()`, so we reload the
        // cached events array when they finish — same pattern as macOS.
        syncCompleteObserver = NotificationCenter.default.addObserver(
            forName: .syncDidComplete,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor [weak self] in
                await self?.refreshUpcomingEvents()
            }
        }

        BackgroundSyncCoordinator.configure(syncService: syncService, settings: settings)
    }

    // MARK: - Lifecycle

    func onAppear() async {
        Logger.app.info("App appeared, refreshing state")
        await refreshState()

        if !settings.onboardingCompleted {
            Logger.app.info("Onboarding not completed, showing setup")
            showOnboarding = true
            return
        }

        Logger.app.info("Foreground sync (authenticated: \(self.isAuthenticated, privacy: .public), calendar: \(String(describing: self.calendarAccessStatus), privacy: .public))")
        await syncService.syncIfStale()
        await refreshUpcomingEvents()
        BackgroundSyncCoordinator.scheduleNextRun()
    }

    /// Reacts to scene transitions. We re-sync on every return-to-foreground
    /// (subject to the staleness window in syncIfStale) so the user never
    /// stares at last-week's events while the app warms up.
    func handleScenePhase(_ phase: ScenePhase) async {
        switch phase {
        case .active:
            guard settings.onboardingCompleted else { return }
            await refreshState()
            await syncService.syncIfStale()
            await refreshUpcomingEvents()
        case .background:
            BackgroundSyncCoordinator.scheduleNextRun()
        case .inactive:
            break
        @unknown default:
            break
        }
    }

    /// Refreshes derived state from keychain + services.
    func refreshState() async {
        hasAPICredentials = keychain.hasAPICredentials()
        isAuthenticated = await authService.isAuthenticated()
        athleteName = await authService.getAthleteName()
        calendarAccessStatus = await calendarService.checkAccessStatus()
    }

    // MARK: - Calendar

    func requestCalendarAccess() async {
        do {
            try await calendarService.requestAccess()
            calendarAccessStatus = .authorized
        } catch {
            calendarAccessStatus = await calendarService.checkAccessStatus()
            errorMessage = error.localizedDescription
        }
    }

    func refreshUpcomingEvents() async {
        // iOS shows every event in the 30-day window; the menu-bar-style cap
        // (settings.maxMenuEvents) is a macOS concern.
        upcomingEvents = await calendarService.getUpcomingEvents(limit: .max)
    }

    func refreshAvailableCalendars() async {
        availableCalendarNames = await calendarService.getAvailableCalendarNames()
    }

    // MARK: - Auth

    func authenticate() async {
        isLoading = true
        errorMessage = nil

        do {
            try await authService.authenticate()
            isAuthenticated = true
            athleteName = await authService.getAthleteName()
            Logger.app.info("Authentication successful")
        } catch AuthError.cancelled {
            Logger.app.info("Authentication cancelled by user")
        } catch {
            Logger.app.error("Authentication failed: \(error.localizedDescription)")
            errorMessage = error.localizedDescription
        }

        isLoading = false
    }

    func disconnect() async {
        do {
            try await authService.disconnect()
            isAuthenticated = false
            athleteName = nil
            settings.syncableClubs = []
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func saveCredentials(clientId: String, clientSecret: String) async {
        do {
            try keychain.save(clientId, for: .clientId)
            try keychain.save(clientSecret, for: .clientSecret)
            hasAPICredentials = true
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    // MARK: - Sync

    func sync() async {
        await syncService.sync()
        await refreshUpcomingEvents()
    }

    func refreshClubs() async {
        isLoading = true
        errorMessage = nil

        do {
            try await syncService.refreshClubs()
        } catch {
            errorMessage = error.localizedDescription
        }

        isLoading = false
    }

    // MARK: - Onboarding

    func completeOnboarding() {
        settings.onboardingCompleted = true
        showOnboarding = false
        BackgroundSyncCoordinator.scheduleNextRun()

        Task {
            await sync()
        }
    }
}

import Foundation
import SwiftUI
import AppKit
import EventKit
import ServiceManagement
import os
import ClubCalendarCore

/// Type alias for clarity.
typealias UpcomingEvent = CalendarEventData

/// Centralized application state.
@MainActor
@Observable
final class AppState {
    // Services
    let stravaService: StravaService
    let calendarService: CalendarService
    let authService: AuthService
    let syncService: SyncService
    let settings: AppSettings
    private let keychain: KeychainHelper
    private var menuOpenObserver: NSObjectProtocol?
    private var syncCompleteObserver: NSObjectProtocol?

    // UI State
    var showSettings = false
    private var onboardingWindow: NSWindow?
    var calendarAccessStatus: CalendarAccessStatus = .notDetermined
    var upcomingEvents: [UpcomingEvent] = []
    var availableCalendarNames: [String] = []
    var isLoading = false
    var errorMessage: String?

    // Auth state
    var isAuthenticated = false
    var athleteName: String?
    var hasAPICredentials = false

    init() {
        let keychain = KeychainHelper.shared
        let settings = AppSettings.shared
        let stravaService = StravaService(keychain: keychain)
        let calendarService = CalendarService(calendarName: settings.calendarName)

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

        // MenuBarExtra(.menu) keeps the SwiftUI view alive for the app's
        // lifetime, so `.task`/`.onAppear` only fire once at launch. Hook the
        // AppKit notification instead so each menu open refreshes the data.
        menuOpenObserver = NotificationCenter.default.addObserver(
            forName: NSMenu.didBeginTrackingNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor [weak self] in
                await self?.refreshOnMenuOpen()
            }
        }

        // Background-scheduler syncs bypass `AppState.sync()`, so we need an
        // explicit signal to reload the cached events array after they finish.
        syncCompleteObserver = NotificationCenter.default.addObserver(
            forName: .syncDidComplete,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor [weak self] in
                await self?.refreshUpcomingEvents()
            }
        }
    }

    // MARK: - Lifecycle

    func onAppear() async {
        Logger.app.info("App appeared, refreshing state")
        await refreshState()
        healOnboardingFlag()

        // Show onboarding if not completed
        if !settings.onboardingCompleted {
            Logger.app.info("Onboarding not completed, showing setup")
            showOnboardingWindow()
        } else {
            Logger.app.info("Starting auto-sync (authenticated: \(self.isAuthenticated, privacy: .public), calendar: \(String(describing: self.calendarAccessStatus), privacy: .public))")
            // Start auto-sync on first appearance; on subsequent menu opens this
            // is a no-op (scheduler already running) but we still opportunistically
            // refresh stale data so the user never sees an outdated menu.
            syncService.startAutoSync()
            await syncService.syncIfStale()
            await refreshUpcomingEvents()
        }
    }

    /// Called each time the user opens the menu bar. Refreshes auth/calendar
    /// state and the cached upcoming events, then syncs if data is stale.
    func refreshOnMenuOpen() async {
        await refreshState()
        // Reload before the sync, which can be slow: the menu must never
        // render stale day groupings, even when onboarding is incomplete.
        await refreshUpcomingEvents()
        guard settings.onboardingCompleted else { return }
        await syncService.syncIfStale()
        await refreshUpcomingEvents()
    }

    /// Refreshes all state from keychain and services.
    ///
    /// Keychain reads stay off the main actor: after a signing-cert rotation
    /// each read blocks inside a SecurityAgent ACL prompt, and a blocked main
    /// thread while the menu is tracking freezes keyboard input system-wide.
    func refreshState() async {
        let keychain = self.keychain
        hasAPICredentials = await Task.detached { keychain.hasAPICredentials() }.value
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
        upcomingEvents = await calendarService.getUpcomingEvents(limit: settings.maxMenuEvents)
    }

    func refreshAvailableCalendars() async {
        availableCalendarNames = await calendarService.getAvailableCalendarNames()
    }

    /// Re-points the calendar service at the newly selected calendar and
    /// re-syncs so events show up there immediately. Without this the service
    /// keeps writing to the calendar chosen at launch until the app restarts.
    func changeCalendar(to name: String) async {
        await calendarService.setCalendarName(name)
        await sync()
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

    // MARK: - Login Item

    func setLoginItemEnabled(_ enabled: Bool) {
        do {
            if enabled {
                try SMAppService.mainApp.register()
            } else {
                try SMAppService.mainApp.unregister()
            }
        } catch {
            errorMessage = "Failed to update login item: \(error.localizedDescription)"
        }
    }

    var isLoginItemEnabled: Bool {
        SMAppService.mainApp.status == .enabled
    }

    // MARK: - Onboarding

    /// Presents onboarding in an AppKit window. A SwiftUI Window scene is not
    /// an option here: on macOS 26.5, declaring one next to MenuBarExtra makes
    /// the app terminate at launch before the status item appears.
    func showOnboardingWindow() {
        if onboardingWindow == nil {
            let window = NSWindow(
                contentViewController: NSHostingController(
                    rootView: OnboardingView().environment(self)
                )
            )
            window.title = "Welcome to Club Calendar"
            window.styleMask = [.titled, .closable]
            window.isReleasedWhenClosed = false
            window.center()
            onboardingWindow = window
        }
        onboardingWindow?.makeKeyAndOrderFront(nil)
        NSApp.activate()
    }

    /// Marks onboarding complete when the install is already configured
    /// (authenticated with calendar access). A missing flag would otherwise
    /// disable auto-sync and menu refresh on a working install.
    func healOnboardingFlag() {
        guard !settings.onboardingCompleted else { return }
        guard isAuthenticated && calendarAccessStatus == .authorized else { return }
        Logger.app.info("Configured install without onboarding flag, marking complete")
        settings.onboardingCompleted = true
    }

    func completeOnboarding() {
        settings.onboardingCompleted = true
        onboardingWindow?.close()
        onboardingWindow = nil
        syncService.startAutoSync()

        Task {
            await sync()
        }
    }
}

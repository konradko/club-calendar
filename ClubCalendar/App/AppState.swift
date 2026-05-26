import Foundation
import SwiftUI
import EventKit
import ServiceManagement
import os

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

    // UI State
    var showOnboarding = false
    var showSettings = false
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
    }

    // MARK: - Lifecycle

    func onAppear() async {
        Logger.app.info("App appeared, refreshing state")
        await refreshState()

        // Show onboarding if not completed
        if !settings.onboardingCompleted {
            Logger.app.info("Onboarding not completed, showing setup")
            showOnboarding = true
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

    /// Refreshes all state from keychain and services.
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
        upcomingEvents = await calendarService.getUpcomingEvents(limit: settings.maxMenuEvents)
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

    func completeOnboarding() {
        settings.onboardingCompleted = true
        showOnboarding = false
        syncService.startAutoSync()

        Task {
            await sync()
        }
    }
}

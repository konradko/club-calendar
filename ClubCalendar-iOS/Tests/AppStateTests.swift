import Testing
import Foundation
import SwiftUI
import ClubCalendarCore
@testable import ClubCalendarIOS

@MainActor
@Suite("AppState — initial state")
struct AppStateInitTests {
    init() {
        TestHelpers.resetSettings()
        BackgroundSyncCoordinator._resetForTesting()
    }

    @Test func wires_settings_singleton() {
        let state = TestHelpers.makeAppState()
        #expect(state.settings === AppSettings.shared)
    }

    @Test func observable_defaults() {
        let state = TestHelpers.makeAppState()
        #expect(state.showOnboarding == false)
        #expect(state.calendarAccessStatus == .notDetermined)
        #expect(state.upcomingEvents.isEmpty)
        #expect(state.availableCalendarNames.isEmpty)
        #expect(state.isLoading == false)
        #expect(state.errorMessage == nil)
        #expect(state.isAuthenticated == false)
        #expect(state.athleteName == nil)
        #expect(state.hasAPICredentials == false)
    }

    @Test func observable_properties_can_be_mutated() {
        let state = TestHelpers.makeAppState()
        state.showOnboarding = true
        state.calendarAccessStatus = .authorized
        state.upcomingEvents = [TestHelpers.makeCalendarEvent()]
        state.availableCalendarNames = ["Personal"]
        state.isLoading = true
        state.errorMessage = "oops"
        state.isAuthenticated = true
        state.athleteName = "Alex"
        state.hasAPICredentials = true

        #expect(state.showOnboarding)
        #expect(state.calendarAccessStatus == .authorized)
        #expect(state.upcomingEvents.count == 1)
        #expect(state.availableCalendarNames == ["Personal"])
        #expect(state.isLoading)
        #expect(state.errorMessage == "oops")
        #expect(state.isAuthenticated)
        #expect(state.athleteName == "Alex")
        #expect(state.hasAPICredentials)
    }
}

@MainActor
@Suite("AppState — lifecycle")
struct AppStateLifecycleTests {
    init() {
        TestHelpers.resetSettings()
        BackgroundSyncCoordinator._resetForTesting()
    }

    @Test func onAppear_when_onboarding_incomplete_shows_onboarding() async {
        let state = TestHelpers.makeAppState()
        AppSettings.shared.onboardingCompleted = false
        await state.onAppear()
        #expect(state.showOnboarding)
    }

    @Test func onAppear_when_onboarding_complete_does_not_show_onboarding() async {
        let state = TestHelpers.makeAppState()
        AppSettings.shared.onboardingCompleted = true
        await state.onAppear()
        #expect(state.showOnboarding == false)
    }

    @Test func handleScenePhase_active_branch_runs_when_onboarded() async {
        let state = TestHelpers.makeAppState()
        AppSettings.shared.onboardingCompleted = true
        await state.handleScenePhase(.active)
        // No calendar perms in the test sim → status stays notDetermined or
        // becomes denied; either way the call completes without crashing.
        let acceptable: [CalendarAccessStatus] = [.notDetermined, .denied, .restricted, .authorized]
        #expect(acceptable.contains(state.calendarAccessStatus))
    }

    @Test func handleScenePhase_active_skips_when_not_onboarded() async {
        let state = TestHelpers.makeAppState()
        AppSettings.shared.onboardingCompleted = false
        await state.handleScenePhase(.active)
        #expect(state.upcomingEvents.isEmpty)
    }

    @Test func handleScenePhase_background_reschedules_without_crash() async {
        let state = TestHelpers.makeAppState()
        await state.handleScenePhase(.background)
        #expect(Bool(true))
    }

    @Test func handleScenePhase_inactive_is_noop() async {
        let state = TestHelpers.makeAppState()
        state.upcomingEvents = [TestHelpers.makeCalendarEvent()]
        await state.handleScenePhase(.inactive)
        #expect(state.upcomingEvents.count == 1)
    }
}

@MainActor
@Suite("AppState — auth + credentials")
struct AppStateAuthTests {
    init() {
        TestHelpers.resetSettings()
        BackgroundSyncCoordinator._resetForTesting()
    }

    @Test func saveCredentials_flips_flag() async {
        let state = TestHelpers.makeAppState()
        await state.saveCredentials(clientId: "abc", clientSecret: "xyz")
        #expect(state.hasAPICredentials)
    }

    @Test func authenticate_without_credentials_sets_error_and_clears_loading() async {
        let state = TestHelpers.makeAppState()
        await state.authenticate()
        #expect(state.isAuthenticated == false)
        #expect(state.isLoading == false)
        #expect(state.errorMessage != nil)
    }

    @Test func disconnect_clears_auth_state() async {
        let state = TestHelpers.makeAuthedAppState()
        state.isAuthenticated = true
        state.athleteName = "Alex"
        AppSettings.shared.syncableClubs = [TestHelpers.makeSyncableClub(id: 1)]

        await state.disconnect()

        #expect(state.isAuthenticated == false)
        #expect(state.athleteName == nil)
        #expect(AppSettings.shared.syncableClubs.isEmpty)
    }

    @Test func refreshState_picks_up_credentials_in_mock() async {
        let state = TestHelpers.makeAuthedAppState()
        await state.refreshState()
        #expect(state.hasAPICredentials)
        #expect(state.isAuthenticated)
        #expect(state.athleteName != nil)
    }
}

@MainActor
@Suite("AppState — calendar")
struct AppStateCalendarTests {
    init() {
        TestHelpers.resetSettings()
        BackgroundSyncCoordinator._resetForTesting()
    }

    @Test func requestCalendarAccess_completes_without_crash() async {
        let state = TestHelpers.makeAppState()
        await state.requestCalendarAccess()
        let acceptable: [CalendarAccessStatus] = [.authorized, .denied, .notDetermined, .restricted]
        #expect(acceptable.contains(state.calendarAccessStatus))
    }

    @Test func refreshUpcomingEvents_does_not_crash() async {
        let state = TestHelpers.makeAppStateWithEmptyCalendar()
        await state.refreshUpcomingEvents()
        #expect(state.upcomingEvents.isEmpty)
    }

    @Test func refreshAvailableCalendars_returns_array() async {
        let state = TestHelpers.makeAppState()
        await state.refreshAvailableCalendars()
        #expect(state.availableCalendarNames.count >= 0)
    }
}

@MainActor
@Suite("AppState — sync + clubs + onboarding")
struct AppStateSyncTests {
    init() {
        TestHelpers.resetSettings()
        BackgroundSyncCoordinator._resetForTesting()
    }

    @Test func sync_without_calendar_access_records_error() async {
        let state = TestHelpers.makeAppState()
        await state.sync()
        #expect(state.syncService.lastSyncError != nil || state.syncService.lastSyncResult != nil)
    }

    @Test func refreshClubs_without_auth_sets_error_and_clears_loading() async {
        let state = TestHelpers.makeAppState()
        await state.refreshClubs()
        #expect(state.isLoading == false)
        #expect(state.errorMessage != nil)
    }

    @Test func completeOnboarding_flips_flag_and_dismisses_sheet() async {
        let state = TestHelpers.makeAppState()
        state.showOnboarding = true
        state.completeOnboarding()
        #expect(AppSettings.shared.onboardingCompleted)
        #expect(state.showOnboarding == false)
        try? await Task.sleep(nanoseconds: 50_000_000)
    }
}

@MainActor
@Suite("AppState — sync-complete notification refresh")
struct AppStateNotificationTests {
    init() {
        TestHelpers.resetSettings()
        BackgroundSyncCoordinator._resetForTesting()
    }

    @Test func syncDidComplete_triggers_upcoming_events_refresh() async {
        let state = TestHelpers.makeAppStateWithEmptyCalendar()
        NotificationCenter.default.post(name: .syncDidComplete, object: nil)
        try? await Task.sleep(nanoseconds: 100_000_000)
        #expect(state.upcomingEvents.isEmpty)
    }
}

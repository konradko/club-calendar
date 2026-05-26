import Testing
import Foundation
@testable import ClubCalendar

@Suite("AppState Tests")
@MainActor
struct AppStateTests {
    // MARK: - Initialization Tests

    @Test("AppState initializes with default values")
    func appStateInitializesWithDefaults() {
        let appState = AppState()

        #expect(appState.showOnboarding == false)
        #expect(appState.showSettings == false)
        #expect(appState.calendarAccessStatus == .notDetermined)
        #expect(appState.upcomingEvents.isEmpty)
        #expect(appState.isLoading == false)
        #expect(appState.errorMessage == nil)
        #expect(appState.isAuthenticated == false)
        #expect(appState.athleteName == nil)
    }

    @Test("AppState has services initialized")
    func appStateServicesInitialized() {
        let appState = AppState()

        // Services should be initialized - accessing them verifies no crash
        _ = appState.stravaService
        _ = appState.calendarService
        _ = appState.authService
        _ = appState.syncService
        _ = appState.settings
    }

    // MARK: - State Property Tests

    @Test("AppState showOnboarding can be set")
    func appStateShowOnboarding() {
        let appState = AppState()

        appState.showOnboarding = true
        #expect(appState.showOnboarding == true)

        appState.showOnboarding = false
        #expect(appState.showOnboarding == false)
    }

    @Test("AppState showSettings can be set")
    func appStateShowSettings() {
        let appState = AppState()

        appState.showSettings = true
        #expect(appState.showSettings == true)

        appState.showSettings = false
        #expect(appState.showSettings == false)
    }

    @Test("AppState calendarAccessStatus can be set")
    func appStateCalendarAccessStatus() {
        let appState = AppState()

        appState.calendarAccessStatus = .authorized
        #expect(appState.calendarAccessStatus == .authorized)

        appState.calendarAccessStatus = .denied
        #expect(appState.calendarAccessStatus == .denied)
    }

    @Test("AppState upcomingEvents can be set")
    func appStateUpcomingEvents() {
        let appState = AppState()
        let events = [
            CalendarEventData(id: "1", title: "Event 1", startDate: Date()),
            CalendarEventData(id: "2", title: "Event 2", startDate: Date())
        ]

        appState.upcomingEvents = events
        #expect(appState.upcomingEvents.count == 2)
        #expect(appState.upcomingEvents[0].title == "Event 1")
    }

    @Test("AppState isLoading can be set")
    func appStateIsLoading() {
        let appState = AppState()

        appState.isLoading = true
        #expect(appState.isLoading == true)

        appState.isLoading = false
        #expect(appState.isLoading == false)
    }

    @Test("AppState errorMessage can be set")
    func appStateErrorMessage() {
        let appState = AppState()

        appState.errorMessage = "Test error"
        #expect(appState.errorMessage == "Test error")

        appState.errorMessage = nil
        #expect(appState.errorMessage == nil)
    }

    @Test("AppState isAuthenticated can be set")
    func appStateIsAuthenticated() {
        let appState = AppState()

        appState.isAuthenticated = true
        #expect(appState.isAuthenticated == true)

        appState.isAuthenticated = false
        #expect(appState.isAuthenticated == false)
    }

    @Test("AppState athleteName can be set")
    func appStateAthleteName() {
        let appState = AppState()

        appState.athleteName = "Test User"
        #expect(appState.athleteName == "Test User")

        appState.athleteName = nil
        #expect(appState.athleteName == nil)
    }

    @Test("AppState hasAPICredentials can be set")
    func appStateHasAPICredentials() {
        let appState = AppState()

        appState.hasAPICredentials = true
        #expect(appState.hasAPICredentials == true)

        appState.hasAPICredentials = false
        #expect(appState.hasAPICredentials == false)
    }

    // MARK: - UpcomingEvent Type Alias

    @Test("UpcomingEvent is CalendarEventData")
    func upcomingEventTypeAlias() {
        let event: UpcomingEvent = CalendarEventData(id: "test", title: "Test", startDate: Date())
        #expect(event.id == "test")
        #expect(event.title == "Test")
    }

    // MARK: - Observable Behavior

    @Test("AppState is Observable")
    func appStateIsObservable() {
        // This test verifies that AppState can be instantiated
        // The @Observable macro is applied at compile time
        let appState = AppState()
        _ = appState  // Use the value to verify instantiation succeeded
    }

    @Test("AppState is MainActor")
    func appStateIsMainActor() async {
        // This test runs on MainActor, verifying AppState can be accessed
        let appState = AppState()
        #expect(appState.isLoading == false)
    }

    // MARK: - CompleteOnboarding Tests

    @Test("completeOnboarding sets onboardingCompleted to true")
    func completeOnboardingSetsFlag() {
        let appState = AppState()
        appState.settings.onboardingCompleted = false
        appState.showOnboarding = true

        appState.completeOnboarding()

        #expect(appState.settings.onboardingCompleted == true)
        #expect(appState.showOnboarding == false)
    }

    // MARK: - Sendable Conformance

    @Test("AppState state changes are isolated to MainActor")
    func appStateMainActorIsolation() async {
        await MainActor.run {
            let appState = AppState()
            appState.isLoading = true
            #expect(appState.isLoading == true)
        }
    }
}

// MARK: - Integration Style Tests

@Suite("AppState Integration Tests")
@MainActor
struct AppStateIntegrationTests {
    @Test("AppState can handle multiple state changes")
    func appStateMultipleStateChanges() {
        let appState = AppState()

        // Simulate a series of state changes
        appState.isLoading = true
        appState.showSettings = true
        appState.isAuthenticated = true
        appState.athleteName = "Test"

        #expect(appState.isLoading == true)
        #expect(appState.showSettings == true)
        #expect(appState.isAuthenticated == true)
        #expect(appState.athleteName == "Test")

        // Reset state
        appState.isLoading = false
        appState.showSettings = false
        appState.isAuthenticated = false
        appState.athleteName = nil

        #expect(appState.isLoading == false)
        #expect(appState.showSettings == false)
        #expect(appState.isAuthenticated == false)
        #expect(appState.athleteName == nil)
    }

    @Test("AppState upcomingEvents can be cleared and repopulated")
    func appStateEventsManagement() {
        let appState = AppState()

        // Add events
        appState.upcomingEvents = [
            CalendarEventData(id: "1", title: "Event 1", startDate: Date())
        ]
        #expect(appState.upcomingEvents.count == 1)

        // Add more events
        appState.upcomingEvents.append(
            CalendarEventData(id: "2", title: "Event 2", startDate: Date())
        )
        #expect(appState.upcomingEvents.count == 2)

        // Clear events
        appState.upcomingEvents = []
        #expect(appState.upcomingEvents.isEmpty)
    }

    @Test("AppState error message flow")
    func appStateErrorFlow() {
        let appState = AppState()

        // No error initially
        #expect(appState.errorMessage == nil)

        // Set error
        appState.errorMessage = "Something went wrong"
        #expect(appState.errorMessage == "Something went wrong")

        // Clear error
        appState.errorMessage = nil
        #expect(appState.errorMessage == nil)
    }
}

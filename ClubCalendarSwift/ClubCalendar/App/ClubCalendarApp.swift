import SwiftUI

@main
struct ClubCalendarApp: App {
    @State private var appState = AppState()

    var body: some Scene {
        // Menu bar
        MenuBarExtra {
            MenuBarView()
                .environment(appState)
        } label: {
            Image(systemName: menuBarIconName)
        }
        .menuBarExtraStyle(.menu)

        // Settings window (SwiftUI Settings scene)
        SwiftUI.Settings {
            SettingsView()
                .environment(appState)
        }

        // Onboarding window
        Window("Welcome to Club Calendar", id: "onboarding") {
            OnboardingView()
                .environment(appState)
        }
        .windowResizability(.contentSize)
        .defaultPosition(.center)
    }

    private var menuBarIconName: String {
        if appState.syncService.syncInProgress {
            return "arrow.triangle.2.circlepath"
        }
        return "calendar.badge.clock"
    }
}

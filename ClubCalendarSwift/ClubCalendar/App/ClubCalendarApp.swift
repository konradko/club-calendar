import SwiftUI
import AppKit

@main
struct ClubCalendarApp: App {
    @State private var appState = AppState()

    var body: some Scene {
        // Menu bar
        MenuBarExtra {
            MenuBarView()
                .environment(appState)
        } label: {
            if appState.syncService.syncInProgress {
                Image(systemName: "arrow.triangle.2.circlepath")
            } else {
                Image(nsImage: menuBarIcon)
            }
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

    private var menuBarIcon: NSImage {
        guard let url = Bundle.main.url(forResource: "icon_menubarTemplate", withExtension: "png"),
              let image = NSImage(contentsOf: url) else {
            // Fallback to SF Symbol if template not found
            return NSImage(systemSymbolName: "calendar.badge.clock", accessibilityDescription: "Club Calendar")!
        }
        image.isTemplate = true
        return image
    }
}

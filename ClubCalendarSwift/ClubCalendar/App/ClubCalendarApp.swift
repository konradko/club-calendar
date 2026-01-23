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
        let image = NSImage(size: NSSize(width: 22, height: 22))

        // Load 1x image
        if let url1x = Bundle.main.url(forResource: "icon_menubarTemplate", withExtension: "png"),
           let rep1x = NSImageRep(contentsOf: url1x) {
            rep1x.size = NSSize(width: 22, height: 22)
            image.addRepresentation(rep1x)
        }

        // Load 2x image
        if let url2x = Bundle.main.url(forResource: "icon_menubarTemplate@2x", withExtension: "png"),
           let rep2x = NSImageRep(contentsOf: url2x) {
            rep2x.size = NSSize(width: 22, height: 22)  // Logical size, not pixel size
            image.addRepresentation(rep2x)
        }

        // Fallback if no images loaded
        if image.representations.isEmpty {
            return NSImage(systemSymbolName: "calendar.badge.clock", accessibilityDescription: "Club Calendar")!
        }

        image.isTemplate = true
        return image
    }
}

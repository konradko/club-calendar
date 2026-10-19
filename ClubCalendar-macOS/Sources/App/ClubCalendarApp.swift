import SwiftUI
import AppKit
import os
import ClubCalendarCore

@main
struct ClubCalendarApp: App {
    @State private var appState = AppState()

    // Force the status item into the menu bar on every launch. Without the
    // isInserted binding, MenuBarExtra terminates the app when the system
    // reports the item as removed (e.g. after the icon was command-dragged
    // off the menu bar), which made every subsequent launch exit instantly.
    @State private var menuBarInserted = true

    init() {
        Logger.app.info("Club Calendar launching")
    }

    var body: some Scene {
        // Menu bar
        MenuBarExtra(isInserted: $menuBarInserted) {
            MenuBarView()
                .environment(appState)
        } label: {
            Group {
                if appState.syncService.syncInProgress {
                    Image(systemName: "arrow.triangle.2.circlepath")
                } else {
                    Image(nsImage: menuBarIcon)
                }
            }
            // On macOS 26.5 the menu content view does not appear at launch,
            // so its .task cannot drive startup. The label is visible from
            // launch, so app startup hooks here.
            .task { await appState.onAppear() }
        }
        .menuBarExtraStyle(.menu)

        // Settings window (SwiftUI Settings scene)
        SwiftUI.Settings {
            SettingsView()
                .environment(appState)
        }

        // Onboarding is an AppKit window owned by AppState, not a Window
        // scene: on macOS 26.5 a Window scene declared next to MenuBarExtra
        // makes the app terminate at launch before the status item appears.
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

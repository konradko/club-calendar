import SwiftUI
import BackgroundTasks
import os
import ClubCalendarCore

@main
struct ClubCalendarApp: App {
    @State private var appState = AppState()
    @Environment(\.scenePhase) private var scenePhase
    // Read directly here (not via AppState) so the scene re-renders the moment
    // the Settings picker writes a new value to the shared UserDefaults key.
    @AppStorage("appearanceMode") private var appearanceMode: AppearanceMode = .system

    init() {
        Logger.app.info("Club Calendar iOS launching")
        BackgroundSyncCoordinator.register()
    }

    var body: some Scene {
        WindowGroup {
            AppRootView()
                .environment(appState)
                .preferredColorScheme(appearanceMode.colorScheme)
                .task {
                    await appState.onAppear()
                }
                .onChange(of: scenePhase) { _, phase in
                    Task { await appState.handleScenePhase(phase) }
                }
        }
    }
}

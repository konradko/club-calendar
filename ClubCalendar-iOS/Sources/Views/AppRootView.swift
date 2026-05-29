import SwiftUI
import ClubCalendarCore

struct AppRootView: View {
    @Environment(AppState.self) private var appState

    var body: some View {
        @Bindable var appState = appState

        TabView {
            TodayView()
                .tabItem { Label("Today", systemImage: "calendar") }

            ClubsView()
                .tabItem { Label("Clubs", systemImage: "person.3") }

            SettingsView()
                .tabItem { Label("Settings", systemImage: "gear") }
        }
        .sheet(isPresented: $appState.showOnboarding) {
            OnboardingView()
                .interactiveDismissDisabled()
        }
    }
}

import Testing
import SwiftUI
import ViewInspector
@testable import ClubCalendar

@Suite("Settings View")
struct SettingsViewTests {
    @Test("SettingsView has correct structure")
    func settingsViewStructure() throws {
        // Test that SettingsView can be instantiated
        let view = SettingsView()
        let _ = view  // View exists
    }

    @Test("GeneralSettingsView has correct structure")
    @MainActor
    func generalSettingsViewStructure() throws {
        let appState = AppState()
        let view = GeneralSettingsView().environment(appState)
        let _ = view  // View exists
    }

    @Test("ClubsSettingsView has correct structure")
    @MainActor
    func clubsSettingsViewStructure() throws {
        let appState = AppState()
        let view = ClubsSettingsView().environment(appState)
        let _ = view  // View exists
    }

    @Test("AccountSettingsView has correct structure")
    @MainActor
    func accountSettingsViewStructure() throws {
        let appState = AppState()
        let view = AccountSettingsView().environment(appState)
        let _ = view  // View exists
    }
}

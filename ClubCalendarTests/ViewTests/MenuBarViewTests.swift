import Testing
import SwiftUI
import ViewInspector
@testable import ClubCalendar

@Suite("MenuBar View")
struct MenuBarViewTests {
    @Test("MenuBarView can be instantiated")
    @MainActor
    func menuBarViewInstantiation() throws {
        let appState = AppState()
        let view = MenuBarView().environment(appState)
        let _ = view  // View exists
    }
}

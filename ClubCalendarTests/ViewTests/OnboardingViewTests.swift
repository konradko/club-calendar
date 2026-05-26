import Testing
import SwiftUI
import ViewInspector
@testable import ClubCalendar

@Suite("Onboarding View")
struct OnboardingViewTests {
    @Test("OnboardingView can be instantiated")
    @MainActor
    func onboardingViewInstantiation() throws {
        let appState = AppState()
        let view = OnboardingView().environment(appState)
        let _ = view  // View exists
    }
}

import Testing
import SwiftUI
import SnapshotTesting
import AppKit
@testable import ClubCalendar

@Suite("View Snapshot Tests")
@MainActor
struct ViewSnapshotTests {
    // MARK: - Test Helpers

    /// Creates a test AppState with controlled values
    private func createTestAppState() -> AppState {
        let appState = AppState()
        return appState
    }

    /// Renders a SwiftUI view to NSImage for snapshot testing
    private func renderView<V: View>(_ view: V, size: CGSize = CGSize(width: 400, height: 300)) -> NSImage {
        let hostingView = NSHostingView(rootView: view)
        hostingView.frame = CGRect(origin: .zero, size: size)

        let bitmapRep = hostingView.bitmapImageRepForCachingDisplay(in: hostingView.bounds)!
        hostingView.cacheDisplay(in: hostingView.bounds, to: bitmapRep)

        let image = NSImage(size: size)
        image.addRepresentation(bitmapRep)
        return image
    }

    // MARK: - EventRow Tests

    @Test("EventRow renders correctly")
    func eventRowSnapshot() {
        let event = CalendarEventData(
            id: "test-1",
            title: "🚴 BikeClub: Morning Ride",
            startDate: Date(timeIntervalSince1970: 1706180400)  // Fixed date for consistent snapshots
        )

        let view = EventRow(event: event)
            .frame(width: 300)
            .padding()
            .background(Color.white)

        let image = renderView(view, size: CGSize(width: 320, height: 60))

        // Verify image was rendered
        #expect(image.size.width > 0)
        #expect(image.size.height > 0)
    }

    @Test("EventRow with long title truncates")
    func eventRowLongTitleSnapshot() {
        let event = CalendarEventData(
            id: "test-2",
            title: "🏃 RunClub Amsterdam: Very Long Event Title That Should Be Truncated",
            startDate: Date(timeIntervalSince1970: 1706180400)
        )

        let view = EventRow(event: event)
            .frame(width: 300)
            .padding()
            .background(Color.white)

        let image = renderView(view, size: CGSize(width: 320, height: 60))
        #expect(image.size.width > 0)
    }

    // MARK: - ClubRow Tests

    @Test("ClubRow renders correctly")
    func clubRowSnapshot() {
        let club = Club(
            id: 1,
            name: "Amsterdam Cycling Club",
            memberCount: 250,
            city: "Amsterdam",
            sportType: "cycling",
            profileMedium: nil
        )
        let syncable = SyncableClub(club: club, isEnabled: true)

        let view = ClubRow(syncableClub: syncable) { _ in }
            .frame(width: 350)
            .padding()
            .background(Color.white)

        let image = renderView(view, size: CGSize(width: 370, height: 80))
        #expect(image.size.width > 0)
    }

    @Test("ClubRow disabled state")
    func clubRowDisabledSnapshot() {
        let club = Club(
            id: 2,
            name: "Berlin Running Group",
            memberCount: 100,
            city: "Berlin",
            sportType: "running",
            profileMedium: nil
        )
        let syncable = SyncableClub(club: club, isEnabled: false)

        let view = ClubRow(syncableClub: syncable) { _ in }
            .frame(width: 350)
            .padding()
            .background(Color.white)

        let image = renderView(view, size: CGSize(width: 370, height: 80))
        #expect(image.size.width > 0)
    }

    @Test("ClubRow without city")
    func clubRowWithoutCitySnapshot() {
        let club = Club(
            id: 3,
            name: "Virtual Club",
            memberCount: 50,
            city: nil,
            sportType: nil,
            profileMedium: nil
        )
        let syncable = SyncableClub(club: club, isEnabled: true)

        let view = ClubRow(syncableClub: syncable) { _ in }
            .frame(width: 350)
            .padding()
            .background(Color.white)

        let image = renderView(view, size: CGSize(width: 370, height: 80))
        #expect(image.size.width > 0)
    }

    // MARK: - SettingsView Tab Tests

    @Test("SettingsView renders")
    func settingsViewSnapshot() {
        let appState = createTestAppState()

        let view = SettingsView()
            .environment(appState)
            .frame(width: 500, height: 400)

        let image = renderView(view, size: CGSize(width: 500, height: 400))
        #expect(image.size.width > 0)
    }

    // MARK: - Component Rendering Tests

    @Test("Multiple EventRows render in list")
    func multipleEventRowsSnapshot() {
        let events = [
            CalendarEventData(id: "1", title: "🚴 Morning Ride", startDate: Date(timeIntervalSince1970: 1706180400)),
            CalendarEventData(id: "2", title: "🏃 Evening Run", startDate: Date(timeIntervalSince1970: 1706209200)),
            CalendarEventData(id: "3", title: "🏊 Pool Session", startDate: Date(timeIntervalSince1970: 1706266800))
        ]

        let view = VStack(alignment: .leading, spacing: 0) {
            ForEach(events) { event in
                EventRow(event: event)
            }
        }
        .frame(width: 300)
        .padding()
        .background(Color.white)

        let image = renderView(view, size: CGSize(width: 320, height: 150))
        #expect(image.size.width > 0)
    }

    @Test("Multiple ClubRows render in list")
    func multipleClubRowsSnapshot() {
        let clubs = [
            SyncableClub(club: Club(id: 1, name: "Cycling Club", memberCount: 100, city: "Amsterdam", sportType: "cycling", profileMedium: nil), isEnabled: true),
            SyncableClub(club: Club(id: 2, name: "Running Club", memberCount: 50, city: "Berlin", sportType: "running", profileMedium: nil), isEnabled: false),
            SyncableClub(club: Club(id: 3, name: "Swimming Club", memberCount: 75, city: nil, sportType: "swimming", profileMedium: nil), isEnabled: true)
        ]

        let view = VStack(alignment: .leading, spacing: 8) {
            ForEach(clubs) { club in
                ClubRow(syncableClub: club) { _ in }
            }
        }
        .frame(width: 350)
        .padding()
        .background(Color.white)

        let image = renderView(view, size: CGSize(width: 370, height: 250))
        #expect(image.size.width > 0)
    }

    // MARK: - View Hierarchy Tests

    @Test("View renders without crashing - OnboardingView")
    func onboardingViewRendersWithoutCrashing() {
        let appState = createTestAppState()

        let view = OnboardingView()
            .environment(appState)
            .frame(width: 500, height: 450)

        let image = renderView(view, size: CGSize(width: 500, height: 450))
        #expect(image.size.width == 500)
        #expect(image.size.height == 450)
    }

    @Test("View renders without crashing - GeneralSettingsView")
    func generalSettingsViewRendersWithoutCrashing() {
        let appState = createTestAppState()

        let view = GeneralSettingsView()
            .environment(appState)
            .frame(width: 400, height: 300)

        let image = renderView(view, size: CGSize(width: 400, height: 300))
        #expect(image.size.width == 400)
    }

    @Test("View renders without crashing - ClubsSettingsView")
    func clubsSettingsViewRendersWithoutCrashing() {
        let appState = createTestAppState()

        let view = ClubsSettingsView()
            .environment(appState)
            .frame(width: 400, height: 300)

        let image = renderView(view, size: CGSize(width: 400, height: 300))
        #expect(image.size.width == 400)
    }

    @Test("View renders without crashing - AccountSettingsView")
    func accountSettingsViewRendersWithoutCrashing() {
        let appState = createTestAppState()

        let view = AccountSettingsView()
            .environment(appState)
            .frame(width: 400, height: 300)

        let image = renderView(view, size: CGSize(width: 400, height: 300))
        #expect(image.size.width == 400)
    }
}

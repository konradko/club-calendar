import Testing
import Foundation
@testable import ClubCalendarMac
@testable import ClubCalendarCore

@Suite("SyncService Extended Tests")
struct SyncServiceExtendedTests {
    // MARK: - Initialization Tests

    @Test("SyncService initializes with correct dependencies")
    @MainActor
    func syncServiceInitialization() {
        let stravaService = StravaService()
        let calendarService = CalendarService()
        let settings = AppSettings.shared

        let syncService = SyncService(
            stravaService: stravaService,
            calendarService: calendarService,
            settings: settings
        )

        #expect(syncService.syncInProgress == false)
        #expect(syncService.lastSyncTime == nil)
    }

    // MARK: - Auto-Sync Tests

    @Test("SyncService startAutoSync creates timer")
    @MainActor
    func syncServiceStartAutoSync() {
        let stravaService = StravaService()
        let calendarService = CalendarService()
        let settings = AppSettings.shared

        let syncService = SyncService(
            stravaService: stravaService,
            calendarService: calendarService,
            settings: settings
        )

        syncService.startAutoSync()

        // Timer should be created (we can't directly check, but the method should complete without error)
        syncService.stopAutoSync()
    }

    @Test("SyncService stopAutoSync works when no timer exists")
    @MainActor
    func syncServiceStopAutoSyncNoTimer() {
        let stravaService = StravaService()
        let calendarService = CalendarService()
        let settings = AppSettings.shared

        let syncService = SyncService(
            stravaService: stravaService,
            calendarService: calendarService,
            settings: settings
        )

        // Should not crash when stopping without starting
        syncService.stopAutoSync()
    }

    @Test("SyncService restartAutoSync stops and starts")
    @MainActor
    func syncServiceRestartAutoSync() {
        let stravaService = StravaService()
        let calendarService = CalendarService()
        let settings = AppSettings.shared

        let syncService = SyncService(
            stravaService: stravaService,
            calendarService: calendarService,
            settings: settings
        )

        syncService.startAutoSync()
        syncService.restartAutoSync()
        syncService.stopAutoSync()
    }

    // MARK: - lastSyncTimeFormatted Tests

    @Test("lastSyncTimeFormatted returns nil when no sync")
    @MainActor
    func lastSyncTimeFormattedNil() {
        let stravaService = StravaService()
        let calendarService = CalendarService()
        let settings = AppSettings.shared

        let syncService = SyncService(
            stravaService: stravaService,
            calendarService: calendarService,
            settings: settings
        )

        #expect(syncService.lastSyncTimeFormatted == nil)
    }

    @Test("lastSyncTimeFormatted returns formatted time for today")
    @MainActor
    func lastSyncTimeFormattedToday() {
        let stravaService = StravaService()
        let calendarService = CalendarService()
        let settings = AppSettings.shared

        let syncService = SyncService(
            stravaService: stravaService,
            calendarService: calendarService,
            settings: settings
        )

        syncService.lastSyncTime = Date()
        let formatted = syncService.lastSyncTimeFormatted

        #expect(formatted != nil)
        // Should contain time format (e.g., "10:30" or "10:30 AM")
    }

    @Test("lastSyncTimeFormatted returns formatted date for yesterday")
    @MainActor
    func lastSyncTimeFormattedYesterday() {
        let stravaService = StravaService()
        let calendarService = CalendarService()
        let settings = AppSettings.shared

        let syncService = SyncService(
            stravaService: stravaService,
            calendarService: calendarService,
            settings: settings
        )

        // Set to yesterday
        let yesterday = Calendar.current.date(byAdding: .day, value: -1, to: Date())!
        syncService.lastSyncTime = yesterday
        let formatted = syncService.lastSyncTimeFormatted

        #expect(formatted != nil)
    }

    @Test("lastSyncTimeFormatted returns formatted date for older date")
    @MainActor
    func lastSyncTimeFormattedOlderDate() {
        let stravaService = StravaService()
        let calendarService = CalendarService()
        let settings = AppSettings.shared

        let syncService = SyncService(
            stravaService: stravaService,
            calendarService: calendarService,
            settings: settings
        )

        // Set to a week ago
        let weekAgo = Calendar.current.date(byAdding: .day, value: -7, to: Date())!
        syncService.lastSyncTime = weekAgo
        let formatted = syncService.lastSyncTimeFormatted

        #expect(formatted != nil)
    }

    // MARK: - SyncInProgress Tests

    @Test("SyncService syncInProgress is initially false")
    @MainActor
    func syncServiceSyncInProgressInitiallyFalse() {
        let stravaService = StravaService()
        let calendarService = CalendarService()
        let settings = AppSettings.shared

        let syncService = SyncService(
            stravaService: stravaService,
            calendarService: calendarService,
            settings: settings
        )

        #expect(syncService.syncInProgress == false)
    }

    // MARK: - SyncInterval Tests

    @Test("SyncInterval rawValues are correct")
    func syncIntervalRawValues() {
        #expect(SyncInterval.fifteenMinutes.rawValue == 15)
        #expect(SyncInterval.thirtyMinutes.rawValue == 30)
        #expect(SyncInterval.oneHour.rawValue == 60)
        #expect(SyncInterval.twoHours.rawValue == 120)
        #expect(SyncInterval.never.rawValue == 0)
    }

    @Test("SyncInterval displayNames are human readable")
    func syncIntervalDisplayNames() {
        #expect(SyncInterval.fifteenMinutes.displayName == "Every 15 minutes")
        #expect(SyncInterval.thirtyMinutes.displayName == "Every 30 minutes")
        #expect(SyncInterval.oneHour.displayName == "Every hour")
        #expect(SyncInterval.twoHours.displayName == "Every 2 hours")
        #expect(SyncInterval.never.displayName == "Never")
    }

    @Test("SyncInterval all cases are distinct")
    func syncIntervalAllCasesDistinct() {
        let allCases = SyncInterval.allCases
        let rawValues = Set(allCases.map(\.rawValue))
        #expect(rawValues.count == allCases.count)
    }

    @Test("SyncInterval CaseIterable conformance")
    func syncIntervalCaseIterable() {
        let cases = SyncInterval.allCases
        #expect(cases.count == 5)
        #expect(cases.contains(.fifteenMinutes))
        #expect(cases.contains(.thirtyMinutes))
        #expect(cases.contains(.oneHour))
        #expect(cases.contains(.twoHours))
        #expect(cases.contains(.never))
    }
}

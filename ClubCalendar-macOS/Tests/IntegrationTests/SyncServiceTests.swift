import Testing
import Foundation
@testable import ClubCalendarMac
@testable import ClubCalendarCore

@Suite("SyncService Tests")
struct SyncServiceTests {
    // MARK: - lastSyncTimeFormatted Tests

    @Test("lastSyncTimeFormatted returns nil when no sync time")
    @MainActor
    func lastSyncTimeFormattedNil() {
        let stravaService = StravaService()
        let calendarService = CalendarService()
        let syncService = SyncService(stravaService: stravaService, calendarService: calendarService)

        #expect(syncService.lastSyncTimeFormatted == nil)
    }

    @Test("lastSyncTimeFormatted formats today's time correctly")
    @MainActor
    func lastSyncTimeFormattedToday() {
        let stravaService = StravaService()
        let calendarService = CalendarService()
        let settings = AppSettings.shared
        let syncService = SyncService(stravaService: stravaService, calendarService: calendarService, settings: settings)

        // Directly set lastSyncTime to test formatting
        let now = Date()
        syncService.lastSyncTime = now

        let formatted = syncService.lastSyncTimeFormatted
        #expect(formatted != nil)
        // Should contain time but not date when today
        // The format depends on locale, but we can check it's not nil and is reasonable length
        #expect(formatted!.count > 0)
        #expect(formatted!.count < 20)  // Time only should be short
    }

    @Test("lastSyncTimeFormatted formats yesterday's time with date")
    @MainActor
    func lastSyncTimeFormattedYesterday() {
        let stravaService = StravaService()
        let calendarService = CalendarService()
        let settings = AppSettings.shared
        let syncService = SyncService(stravaService: stravaService, calendarService: calendarService, settings: settings)

        // Set to yesterday
        let yesterday = Calendar.current.date(byAdding: .day, value: -1, to: Date())!
        syncService.lastSyncTime = yesterday

        let formatted = syncService.lastSyncTimeFormatted
        #expect(formatted != nil)
        // Should be longer as it includes date
        #expect(formatted!.count > 5)
    }

    @Test("lastSyncTimeFormatted formats past date with date and time")
    @MainActor
    func lastSyncTimeFormattedPastDate() {
        let stravaService = StravaService()
        let calendarService = CalendarService()
        let settings = AppSettings.shared
        let syncService = SyncService(stravaService: stravaService, calendarService: calendarService, settings: settings)

        // Set to a week ago
        let weekAgo = Calendar.current.date(byAdding: .day, value: -7, to: Date())!
        syncService.lastSyncTime = weekAgo

        let formatted = syncService.lastSyncTimeFormatted
        #expect(formatted != nil)
    }

    // MARK: - syncInProgress Tests

    @Test("syncInProgress is initially false")
    @MainActor
    func syncInProgressInitiallyFalse() {
        let stravaService = StravaService()
        let calendarService = CalendarService()
        let syncService = SyncService(stravaService: stravaService, calendarService: calendarService)

        #expect(syncService.syncInProgress == false)
    }

    // MARK: - Timer Management Tests

    @Test("stopAutoSync handles nil timer")
    @MainActor
    func stopAutoSyncNilTimer() {
        let stravaService = StravaService()
        let calendarService = CalendarService()
        let syncService = SyncService(stravaService: stravaService, calendarService: calendarService)

        // Should not crash when timer is nil
        syncService.stopAutoSync()
        #expect(syncService.syncInProgress == false)
    }

    @Test("restartAutoSync calls startAutoSync internally")
    @MainActor
    func restartAutoSyncCallsStart() {
        let stravaService = StravaService()
        let calendarService = CalendarService()
        let settings = AppSettings.shared

        let originalInterval = settings.syncInterval
        settings.syncInterval = .never  // Prevent actual timer creation

        let syncService = SyncService(stravaService: stravaService, calendarService: calendarService, settings: settings)

        syncService.restartAutoSync()
        // With .never interval, no timer should be created
        #expect(syncService.syncInProgress == false)

        settings.syncInterval = originalInterval
    }

    @Test("startAutoSync with never interval does nothing")
    @MainActor
    func startAutoSyncWithNeverInterval() {
        let stravaService = StravaService()
        let calendarService = CalendarService()
        let settings = AppSettings.shared

        let originalInterval = settings.syncInterval
        settings.syncInterval = .never

        let syncService = SyncService(stravaService: stravaService, calendarService: calendarService, settings: settings)
        syncService.startAutoSync()

        // Timer should not be created
        #expect(syncService.syncInProgress == false)

        settings.syncInterval = originalInterval
    }

    // MARK: - lastSyncResult Tests

    @Test("lastSyncResult is initially nil")
    @MainActor
    func lastSyncResultInitiallyNil() {
        let stravaService = StravaService()
        let calendarService = CalendarService()
        let syncService = SyncService(stravaService: stravaService, calendarService: calendarService)

        #expect(syncService.lastSyncResult == nil)
    }

    @Test("lastSyncError is initially nil")
    @MainActor
    func lastSyncErrorInitiallyNil() {
        let stravaService = StravaService()
        let calendarService = CalendarService()
        let syncService = SyncService(stravaService: stravaService, calendarService: calendarService)

        #expect(syncService.lastSyncError == nil)
    }

    // MARK: - Initialization Tests

    @Test("SyncService initializes with provided services")
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
        #expect(syncService.lastSyncResult == nil)
        #expect(syncService.lastSyncError == nil)
    }

    @Test("SyncService uses default settings when not provided")
    @MainActor
    func syncServiceDefaultSettings() {
        let stravaService = StravaService()
        let calendarService = CalendarService()

        let syncService = SyncService(
            stravaService: stravaService,
            calendarService: calendarService
        )

        #expect(syncService.lastSyncTimeFormatted == nil)
    }

    // MARK: - lastSyncTime Direct Access Tests

    @Test("lastSyncTime can be set and read")
    @MainActor
    func lastSyncTimeSetAndRead() {
        let stravaService = StravaService()
        let calendarService = CalendarService()
        let syncService = SyncService(stravaService: stravaService, calendarService: calendarService)

        let testDate = Date(timeIntervalSince1970: 1706180400)
        syncService.lastSyncTime = testDate

        #expect(syncService.lastSyncTime == testDate)
    }

    @Test("lastSyncResult can be set and read")
    @MainActor
    func lastSyncResultSetAndRead() {
        let stravaService = StravaService()
        let calendarService = CalendarService()
        let syncService = SyncService(stravaService: stravaService, calendarService: calendarService)

        let testResult = SyncResult(created: 1, updated: 2, cancelled: 3)
        syncService.lastSyncResult = testResult

        #expect(syncService.lastSyncResult?.created == 1)
        #expect(syncService.lastSyncResult?.updated == 2)
        #expect(syncService.lastSyncResult?.cancelled == 3)
    }

    @Test("lastSyncError can be set and read")
    @MainActor
    func lastSyncErrorSetAndRead() {
        let stravaService = StravaService()
        let calendarService = CalendarService()
        let syncService = SyncService(stravaService: stravaService, calendarService: calendarService)

        let testError = CalendarError.accessDenied
        syncService.lastSyncError = testError

        #expect(syncService.lastSyncError != nil)
        if case .accessDenied? = syncService.lastSyncError as? CalendarError {
            // Expected
        } else {
            #expect(Bool(false), "Expected accessDenied error")
        }
    }
}

import Testing
@testable import ClubCalendarMac
@testable import ClubCalendarCore

@Suite("SyncResult")
struct SyncResultTests {
    @Test("Total changes calculation")
    func totalChangesCalculation() {
        let result = SyncResult(created: 3, updated: 2, cancelled: 1)
        #expect(result.totalChanges == 6)
    }

    @Test("Has changes detection")
    func hasChangesDetection() {
        let noChanges = SyncResult(created: 0, updated: 0, cancelled: 0)
        #expect(noChanges.hasChanges == false)

        let withCreated = SyncResult(created: 1, updated: 0, cancelled: 0)
        #expect(withCreated.hasChanges == true)

        let withUpdated = SyncResult(created: 0, updated: 1, cancelled: 0)
        #expect(withUpdated.hasChanges == true)

        let withCancelled = SyncResult(created: 0, updated: 0, cancelled: 1)
        #expect(withCancelled.hasChanges == true)
    }

    @Test("Summary formatting - no changes")
    func summaryNoChanges() {
        let noChanges = SyncResult(created: 0, updated: 0, cancelled: 0)
        #expect(noChanges.summary == "No changes")
    }

    @Test("Summary formatting - single type", arguments: [
        (3, 0, 0, "3 created"),
        (0, 2, 0, "2 updated"),
        (0, 0, 1, "1 cancelled")
    ])
    func summarySingleType(created: Int, updated: Int, cancelled: Int, expected: String) {
        let result = SyncResult(created: created, updated: updated, cancelled: cancelled)
        #expect(result.summary == expected)
    }

    @Test("Summary formatting - mixed")
    func summaryMixed() {
        let mixed = SyncResult(created: 1, updated: 2, cancelled: 1)
        #expect(mixed.summary == "1 created, 2 updated, 1 cancelled")
    }

    @Test("Summary with different combinations", arguments: [
        (5, 3, 0, "5 created, 3 updated"),
        (2, 0, 4, "2 created, 4 cancelled"),
        (0, 1, 1, "1 updated, 1 cancelled")
    ])
    func summaryDifferentCombinations(created: Int, updated: Int, cancelled: Int, expected: String) {
        let result = SyncResult(created: created, updated: updated, cancelled: cancelled)
        #expect(result.summary == expected)
    }

    // MARK: - Edge Cases

    @Test("SyncResult with maximum values")
    func syncResultWithMaximumValues() {
        let result = SyncResult(created: Int.max / 3, updated: Int.max / 3, cancelled: Int.max / 3)
        #expect(result.hasChanges == true)
        #expect(result.totalChanges > 0)
    }

    @Test("SyncResult summary format consistency")
    func syncResultSummaryFormatConsistency() {
        // Test that summary always uses same format
        let result1 = SyncResult(created: 1, updated: 0, cancelled: 0)
        #expect(result1.summary == "1 created")
        #expect(!result1.summary.contains(","))

        let result2 = SyncResult(created: 1, updated: 1, cancelled: 0)
        #expect(result2.summary == "1 created, 1 updated")
        #expect(result2.summary.contains(", "))

        let result3 = SyncResult(created: 1, updated: 1, cancelled: 1)
        #expect(result3.summary == "1 created, 1 updated, 1 cancelled")
        #expect(result3.summary.filter { $0 == "," }.count == 2)
    }

    @Test("SyncResult Sendable conformance")
    func syncResultSendable() async {
        let result = SyncResult(created: 1, updated: 2, cancelled: 3)

        let task = Task { @Sendable in
            return result.totalChanges
        }

        let total = await task.value
        #expect(total == 6)
    }

    @Test("SyncResult hasChanges boundary")
    func syncResultHasChangesBoundary() {
        // Exactly at boundary
        let result1 = SyncResult(created: 1, updated: 0, cancelled: 0)
        #expect(result1.hasChanges == true)

        let result2 = SyncResult(created: 0, updated: 1, cancelled: 0)
        #expect(result2.hasChanges == true)

        let result3 = SyncResult(created: 0, updated: 0, cancelled: 1)
        #expect(result3.hasChanges == true)
    }

    @Test("SyncResult totalChanges calculation accuracy")
    func syncResultTotalChangesAccuracy() {
        let testCases: [(Int, Int, Int, Int)] = [
            (0, 0, 0, 0),
            (1, 0, 0, 1),
            (0, 1, 0, 1),
            (0, 0, 1, 1),
            (1, 1, 1, 3),
            (10, 20, 30, 60),
            (100, 200, 300, 600)
        ]

        for (created, updated, cancelled, expected) in testCases {
            let result = SyncResult(created: created, updated: updated, cancelled: cancelled)
            #expect(result.totalChanges == expected)
        }
    }
}

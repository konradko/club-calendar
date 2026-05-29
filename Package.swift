// swift-tools-version: 6.2

import PackageDescription

let package = Package(
    name: "ClubCalendar",
    platforms: [
        .macOS(.v26),
        .iOS(.v26)
    ],
    products: [
        // The macOS executable's product (binary) name stays "ClubCalendar"
        // so the user-facing .app bundle is unchanged. The SPM target is
        // renamed for symmetry with the iOS Xcode target (ClubCalendarIOS).
        .executable(name: "ClubCalendar", targets: ["ClubCalendarMac"]),
        .library(name: "ClubCalendarCore", targets: ["ClubCalendarCore"])
    ],
    dependencies: [
        .package(url: "https://github.com/nalexn/ViewInspector.git", from: "0.10.0"),
        .package(url: "https://github.com/pointfreeco/swift-snapshot-testing.git", from: "1.15.0")
    ],
    targets: [
        .target(
            name: "ClubCalendarCore",
            dependencies: [],
            path: "ClubCalendarCore",
            swiftSettings: [
                .enableExperimentalFeature("StrictConcurrency")
            ]
        ),
        .executableTarget(
            name: "ClubCalendarMac",
            dependencies: ["ClubCalendarCore"],
            path: "ClubCalendar-macOS/Sources",
            resources: [
                .process("Resources")
            ],
            swiftSettings: [
                .enableExperimentalFeature("StrictConcurrency")
            ]
        ),
        .testTarget(
            name: "ClubCalendarMacTests",
            dependencies: [
                "ClubCalendarMac",
                "ClubCalendarCore",
                .product(name: "ViewInspector", package: "ViewInspector"),
                .product(name: "SnapshotTesting", package: "swift-snapshot-testing")
            ],
            path: "ClubCalendar-macOS/Tests"
        )
    ]
)

// swift-tools-version: 6.2

import PackageDescription

let package = Package(
    name: "ClubCalendar",
    platforms: [
        .macOS(.v26)
    ],
    products: [
        .executable(name: "ClubCalendar", targets: ["ClubCalendar"])
    ],
    dependencies: [
        .package(url: "https://github.com/nalexn/ViewInspector.git", from: "0.10.0"),
        .package(url: "https://github.com/pointfreeco/swift-snapshot-testing.git", from: "1.15.0")
    ],
    targets: [
        .executableTarget(
            name: "ClubCalendar",
            dependencies: [],
            path: "ClubCalendar",
            resources: [
                .process("Resources")
            ],
            swiftSettings: [
                .enableExperimentalFeature("StrictConcurrency")
            ]
        ),
        .testTarget(
            name: "ClubCalendarTests",
            dependencies: [
                "ClubCalendar",
                .product(name: "ViewInspector", package: "ViewInspector"),
                .product(name: "SnapshotTesting", package: "swift-snapshot-testing")
            ],
            path: "ClubCalendarTests"
        )
    ]
)

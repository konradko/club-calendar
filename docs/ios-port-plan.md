# iOS Port Plan

Personal-use iOS version of the macOS Club Calendar menu bar app.

## Decisions

- **Repo layout:** same repo, shared `ClubCalendarCore` SPM library consumed by both the macOS executable and a new iOS Xcode project
- **Background sync:** `BGAppRefreshTask` + sync-on-foreground (no backend, no push)
- **Widget:** not in v1
- **iOS deployment target:** iOS 26+ (mirrors macOS 26; we're shipping to a personally-owned iPhone 16 Pro Max on iOS 26.5)

## What ports as-is

The entire non-UI stack is already portable (actor-based, Sendable, protocol-bounded, zero AppKit imports):

- `Services/StravaService.swift`, `AuthService.swift`, `CalendarService.swift`, `Protocols.swift`
- `Utilities/KeychainHelper.swift` (with one storage-attribute swap, see below)
- `Models/*` — `Club`, `ClubEvent`, `Settings`
- All `ClubCalendarTests/` mocks (`MockURLSession`, `MockKeychainHelper`)
- OAuth callback URL scheme `clubcalendar://`
- `ASWebAuthenticationSession` (same API on iOS)

## What needs replacing

| macOS bit | iOS replacement | Notes |
|---|---|---|
| `MenuBarExtra` + `NSMenu` observers | `NavigationStack` + `TabView` | Whole `MenuBarView` redesigned |
| `NSBackgroundActivityScheduler` | `BGAppRefreshTask` + `scenePhase == .active` | iOS background is best-effort, surface that in UI |
| `NSWorkspace.didWakeNotification` | `scenePhase` transitions | Resume → sync if stale |
| File-based keychain (`SecKeychain` legacy) | Standard data-protection keychain | Use `kSecAttrAccessibleAfterFirstUnlock`; legacy file keychain doesn't exist on iOS |
| `SMAppService` login item | Delete | No equivalent, not needed |
| Calendar full-access (macOS 14+ API) | Same API (`requestFullAccessToEvents`, iOS 17+) | Add `NSCalendarsFullAccessUsageDescription` to iOS Info.plist |
| `Makefile` bundling + self-signed cert | Xcode project | iOS needs real provisioning |

## Target structure

```
Package.swift
  ├── ClubCalendarCore         (library)     ← Services, Models, Utilities
  ├── ClubCalendarMac          (executable)  ← macOS @main + Views
  └── ClubCalendarCoreTests

ClubCalendar-iOS.xcodeproj                   ← iOS target, local package dep on ClubCalendarCore
  └── Views/  (iOS-specific SwiftUI)
```

## iOS UI shape

```
TabView
├── Today        — upcoming events grouped by day (port MenuBarView body)
├── Clubs        — toggle-list of joined clubs (port ClubsSettingsView)
└── Settings     — sync interval, account, calendar status

OnboardingSheet  — 4-step wizard, unchanged from macOS
```

`AppState` on iOS:
- Drop `MenuBarExtra` plumbing and `NSMenu.didBeginTrackingNotification`
- Drop `SMAppService` block
- Wire `scenePhase` observation for foreground sync
- Register `BGAppRefreshTask` in app delegate

## Phased plan

| # | Phase | Status | Output |
|---|---|---|---|
| 1 | Extract `ClubCalendarCore` library | ✅ done | `Services/`, `Models/`, `Utilities/` live under `ClubCalendarCore/`; macOS app + 436 tests pass |
| 2 | Create iOS Xcode project | ✅ done | `ClubCalendar-iOS/project.yml` (xcodegen); generates `ClubCalendar-iOS.xcodeproj` with bundle id `com.clubcalendar.ios`, `clubcalendar://` URL scheme, `NSCalendarsUsageDescription` + `NSCalendarsFullAccessUsageDescription`, `BGTaskSchedulerPermittedIdentifiers = ["com.clubcalendar.sync"]`, local SPM dep on `ClubCalendarCore` |
| 3 | Port `AppState` to iOS | ✅ done | `ClubCalendar-iOS/Sources/AppState.swift` wired to `scenePhase` via `handleScenePhase(_:)`; no MenuBarExtra/SMAppService |
| 4 | Build iOS views | ✅ done | `AppRootView` (TabView) + `TodayView`, `ClubsView`, `SettingsView`, `OnboardingView` |
| 5 | Background sync | ✅ done | `BackgroundSync.swift` registers `com.clubcalendar.sync`; reschedules on background + after each run |
| 6 | Manual test on device | ⏳ on you | Open the generated xcodeproj in Xcode, set signing team, build to device/simulator, run the OAuth + calendar grant flow |

## One-time machine setup

This Mac is missing the iOS Simulator runtime/CoreSimulator framework. Before building from the command line or running the simulator, run:

```
sudo xcodebuild -runFirstLaunch
```

After that, the iOS app builds via Xcode directly (open `ClubCalendar-iOS/ClubCalendar-iOS.xcodeproj`) or via:

```
xcodegen generate    # only if you edited project.yml
xcodebuild -project ClubCalendar-iOS/ClubCalendar-iOS.xcodeproj \
           -scheme ClubCalendar \
           -destination "generic/platform=iOS Simulator" build
```

The iOS sources have been type-checked against the iPhoneOS 26.5 SDK successfully (clean — no errors), so any build issues will be linking/signing, not source code.

**Total:** ~5 working days estimated, scaffolded same-day.

## Reference: macOS dependencies to strip

When porting any service/view file, watch for:
- `import AppKit`
- `NSApplication.shared` — used in `AuthService.swift:123` for presentation context fallback
- `NSBackgroundActivityScheduler` — `SyncService.swift:54`
- `NSWorkspace.didWakeNotification` — `SyncService.swift:73`
- `MenuBarExtra`, `NSMenu.didBeginTrackingNotification` — `AppState.swift:59`
- `SMAppService` — `AppState.swift:205`
- `platforms: [.macOS(.v26)]` constraint in `Package.swift`

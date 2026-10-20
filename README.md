<p align="center">
  <img src="icon/icon.svg" alt="Club Calendar" width="128" height="128">
</p>

# Club Calendar

A macOS menu bar app that syncs your Strava club events to Apple Calendar.

Native SwiftUI, no background daemons, no third-party runtime dependencies.

## Features

- Mirrors events from all your Strava clubs into a dedicated calendar
- Native EventKit integration; events open in Apple Calendar or on Strava
- Auto-sync on a configurable interval, with wake-from-sleep catch-up
- Per-club enable/disable in Settings
- Self-healing dedup of events created by previous syncs

## Installation

### Build from source

```bash
git clone https://github.com/konradko/club-calendar
cd club-calendar
make macos-dmg
```

`make macos-dmg` builds a signed release app, packs it into `ClubCalendar.dmg` and opens the DMG. Drag **ClubCalendar** to Applications and launch it.

Requires macOS 26+ and Swift 6.2 (Xcode 26).

### iOS

There's also an iOS app sharing the same `ClubCalendarCore` logic. See
[docs/ios-app.md](docs/ios-app.md) for how it's built and how it works, and
[docs/ios-install.md](docs/ios-install.md) to put it on your iPhone.

## Setup

1. **Get Strava API credentials** at [strava.com/settings/api](https://www.strava.com/settings/api). Strava allows one API application per account — the same one serves both the macOS and iOS apps. Set its **Authorization Callback Domain** to `callback` (a bare host, no scheme or slashes) — this must match the host of the app's `clubcalendar://callback` redirect URI. Note your Client ID and Client Secret.
2. **Launch the app** — onboarding will walk you through entering credentials, authenticating with Strava, picking clubs to sync, and granting Calendar access.

Credentials and OAuth tokens are stored in the Keychain. On macOS this is the legacy file keychain (see [keychain notes](#why-the-legacy-file-keychain)). On iOS it is the data-protection keychain.

## Project layout

```
ClubCalendarCore/        # Shared library for both apps
├── Models/              # Club, ClubEvent, Settings
├── Services/            # StravaService, CalendarService, AuthService, SyncService, Protocols
└── Utilities/           # Logger, ActivityEmoji, KeychainHelper
ClubCalendar-macOS/
├── Sources/
│   ├── App/             # ClubCalendarApp (SwiftUI @main), AppState
│   ├── Views/           # MenuBarView, SettingsView (+ Settings/ tabs), OnboardingView
│   └── Resources/       # Icons, entitlements
└── Tests/               # ClubCalendarMacTests (macOS + Core tests)
ClubCalendar-iOS/
├── Sources/             # ClubCalendarApp (@main), AppState, BackgroundSync, Views/
├── Tests/               # ClubCalendarIOSTests
└── project.yml          # xcodegen spec for the Xcode project
Package.swift            # SwiftPM: ClubCalendarCore, ClubCalendarMac, ClubCalendarMacTests
Makefile                 # build / bundle / sign / dmg / dev / test, macOS and iOS
```

## Architecture

```
ClubCalendarApp (SwiftUI @main)
  └── AppState (@MainActor @Observable — composition root + UI state)
        ├── KeychainHelper          ← legacy file keychain, kSecAttrAccessibleAfterFirstUnlock
        ├── AppSettings             ← @AppStorage + JSON-encoded clubs
        ├── StravaService (actor)   ← HTTPS to www.strava.com/api/v3
        ├── CalendarService (actor) ← EventKit
        ├── AuthService             ← ASWebAuthenticationSession (clubcalendar://callback)
        └── SyncService             ← NSBackgroundActivityScheduler + wake notification
```

Sync flow: `SyncService.sync()` → `StravaService.getEventsForClubs(...)` (parallel per club) → `CalendarService.syncEvents(...)` (dedup by Strava ID embedded in `EKEvent.url`, mark removed future events `[CANCELLED]`). Clubs whose fetch failed are skipped by the cancel step, so a network error never cancels their events.

## Development

```bash
make macos-dev      # build debug, bundle, sign, open
make test           # run the full test matrix (macOS + iOS)
make macos-test     # macOS/Core tests only (FILTER=X narrows to matching tests)
make macos-restart  # kill, rebuild, reopen
make macos-logs     # stream unified logs (subsystem com.clubcalendar.app)
make macos-dmg      # signed release DMG with /Applications shortcut
make lint           # swift-format lint (config in .swift-format)
```

Run `make help` for the full target list.

### Permissions across installs and updates

macOS ties both the Calendar (TCC) grant and keychain-item ACLs to the app's
signing identity. All builds are therefore signed with one stable self-signed
certificate, created on first build by `scripts/create-dev-cert.sh` (via
`make macos-setup-cert`, valid 10 years). As long as that identity is stable,
you grant Calendar access once and never see keychain prompts, across
rebuilds, updates, and reinstalls.

If the identity ever rotates (cert deleted or expired), expect a one-time
Calendar re-prompt and per-item keychain dialogs; click **Always Allow**, or
run `make macos-reset-all` to start clean. Signing intentionally has no
ad-hoc fallback: a missing cert fails the build rather than silently
producing an app that resets your permissions.

### Why the legacy file keychain

On macOS 26 the data-protection keychain (`keychain-access-groups` entitlement) requires a provisioning profile, which self-signed dev builds don't have. We use the legacy file keychain instead. See `KeychainHelper.swift` for details.

## License

MIT

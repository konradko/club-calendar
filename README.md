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

### Download

Grab the latest DMG from [Releases](https://github.com/konradko/club-calendar/releases), open it, drag **Club Calendar** to Applications, and launch.

### Build from source

```bash
git clone https://github.com/konradko/club-calendar
cd club-calendar
make dmg
```

Requires macOS 26+ and Swift 6.2 (Xcode 26).

## Setup

1. **Get Strava API credentials** at [strava.com/settings/api](https://www.strava.com/settings/api). Strava allows one API application per account — the same one serves both the macOS and iOS apps. Set its **Authorization Callback Domain** to `callback` (a bare host, no scheme or slashes) — this must match the host of the app's `clubcalendar://callback` redirect URI. Note your Client ID and Client Secret.
2. **Launch the app** — onboarding will walk you through entering credentials, authenticating with Strava, picking clubs to sync, and granting Calendar access.

Credentials and OAuth tokens are stored in the macOS Keychain (data-protection-style legacy file keychain — see [keychain notes](#why-the-legacy-file-keychain)).

## Project layout

```
ClubCalendar/
├── App/         # ClubCalendarApp (SwiftUI @main), AppState
├── Models/      # Club, ClubEvent, Settings
├── Services/    # StravaService, CalendarService, AuthService, SyncService, KeychainHelper
├── Views/       # MenuBarView, SettingsView (+ subviews), OnboardingView
├── Utilities/   # Logger, ActivityEmoji
└── Resources/   # Icons, entitlements
ClubCalendarTests/
Makefile         # build / bundle / sign / dmg / dev / test
```

## Architecture

```
ClubCalendarApp (SwiftUI @main)
  └── AppState (@MainActor @Observable — composition root + UI state)
        ├── KeychainHelper          ← legacy file keychain, kSecAttrAccessibleAfterFirstUnlock
        ├── AppSettings             ← @AppStorage + JSON-encoded clubs
        ├── StravaService (actor)   ← HTTPS to api.strava.com
        ├── CalendarService (actor) ← EventKit
        ├── AuthService             ← ASWebAuthenticationSession (clubcalendar://callback)
        └── SyncService             ← NSBackgroundActivityScheduler + wake notification
```

Sync flow: `SyncService.sync()` → `StravaService.getEventsForClubs(...)` (parallel per club) → `CalendarService.syncEvents(...)` (dedup by Strava ID embedded in `EKEvent.url`, mark removed future events `[CANCELLED]`).

## Development

```bash
make dev      # build debug, bundle, sign, open
make test     # run XCTest / swift-testing suite
make restart  # kill, rebuild, reopen
make logs     # stream unified logs (subsystem com.clubcalendar.app)
make dmg      # signed release DMG with /Applications shortcut
```

The dev signing cert is created locally by `scripts/create-dev-cert.sh` — `make setup-cert` regenerates it. Keychain ACLs are tied to the signing identity, so a stable dev cert means no repeated keychain prompts.

### Why the legacy file keychain

On macOS 26 the data-protection keychain (`keychain-access-groups` entitlement) requires a provisioning profile, which self-signed dev builds don't have. We use the legacy file keychain instead. See `KeychainHelper.swift` for details.

## License

MIT

# macOS Menu Bar App

Build and distribute the Club Calendar menu bar app as a DMG.

## Build DMG

```bash
cd deploy/macos-menubar
make dmg
```

Output: `dist/ClubCalendar-{version}.dmg`

## Install

1. Open `dist/ClubCalendar-0.1.0.dmg`
2. Drag Club Calendar to Applications
3. Open from Applications

## Start at Login

Use the **Start at Login** option in the app menu to enable/disable automatic startup.

## Development

Run from source without building:

```bash
uv run club-calendar-menubar
```

## Features

- One-click calendar sync
- Setup wizard (no CLI required):
  - Configure Strava API credentials
  - OAuth authentication
  - Club selection
- Auto-sync every hour
- Start at Login toggle
- Status indicator in menu bar
- macOS notifications

## Getting Strava Credentials

1. Go to [strava.com/settings/api](https://www.strava.com/settings/api)
2. Create an application (use `localhost` for callback URL)
3. Note your **Client ID** and **Client Secret**

Then in the menu bar app: Setup > Configure Strava API...

## Build Requirements

- macOS
- PyInstaller (`uv sync` installs it)
- Xcode Command Line Tools (for `hdiutil`)

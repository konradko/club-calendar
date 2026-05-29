# Installing Club Calendar on your iPhone

Personal-use sideload via Xcode. **No App Store, no TestFlight, no paid Apple Developer Program required.** A free Apple ID is enough. This guide covers the full path: create the free Personal Team, validate in the simulator, sideload to the phone, and what to do when the cert expires.

---

## TL;DR

```bash
# One-time setup
xcode-select --install                          # if you haven't already
# Open Xcode → Settings → Accounts → "+" → sign in with your free Apple ID
export DEVELOPMENT_TEAM=ABCD123XYZ              # see step 1 below to find it
# In ~/.zshrc: add the export so future shells inherit it

# Validate in the simulator first
make ios-run                                    # builds + boots sim + launches

# Then install on the phone
xcrun devicectl list devices                    # confirm phone is connected
make ios-install-device                         # archives + installs
# On the phone: Settings → General → VPN & Device Management → trust your Apple ID
```

---

## 1. One-time setup

### a. Get a free Apple Developer "Personal Team"

You don't need to pay $99/year. The free path:

1. Open **Xcode → Settings → Accounts**.
2. Click `+` → **Apple ID** → sign in with whatever Apple ID you use on your iPhone (it must be the same one).
3. Xcode auto-creates a **Personal Team** under that Apple ID. It shows up in the Team list with a name like "Konrad (Personal Team)".
4. Click the team row to see the **Team ID** — a 10-character alphanumeric string (e.g. `7K2X4P9JD3`).

Export it so the Makefile picks it up:

```bash
echo 'export DEVELOPMENT_TEAM=7K2X4P9JD3' >> ~/.zshrc      # your actual ID
source ~/.zshrc
```

### b. Trust this Mac from the iPhone

1. Plug the iPhone into the Mac via USB-C (or Lightning).
2. The phone shows "**Trust this Computer?**" — tap **Trust**, enter the passcode.
3. Verify from the Mac side:

   ```bash
   xcrun devicectl list devices
   ```

   You should see a row with your iPhone's name, OS version, and a UUID. If the phone isn't listed, unplug + replug and re-trust.

### c. (First install only) Generate a provisioning profile via Xcode

`make ios-install-device` will attempt to do this for you, but the very first time it can fail because Xcode hasn't talked to Apple's signing servers for your bundle ID yet. If `make ios-install-device` errors with "no profile found":

1. `open ClubCalendar-iOS/ClubCalendar-iOS.xcodeproj`
2. In the navigator, select the **ClubCalendar** target (top-level).
3. Click **Signing & Capabilities** at the top.
4. Check **Automatically manage signing**.
5. Pick your Personal Team from the dropdown.
6. Wait ~5 seconds. Xcode talks to Apple, registers the bundle ID, downloads a provisioning profile. You should see a green "Provisioning Profile: Xcode Managed" line below.
7. Close Xcode and re-run `make ios-install-device`.

---

## 2. Validate in the simulator first

Before touching the phone, smoke-test the app in the simulator. Sim and device behave identically for everything except real BG refresh timing, so this catches ~95% of issues.

```bash
make ios-run
```

What this does:

1. Boots the **iPhone 17 Pro Max** simulator (Apple ships only iPhone-17-series sims with the iOS 26.5 SDK — geometrically identical to your iPhone 16 Pro Max).
2. Builds debug iOS app.
3. Installs the freshly-built `ClubCalendar.app` on the sim.
4. Launches it.

Walk through the onboarding using your real Strava credentials:

1. Paste your **Strava Client ID** and **Client Secret** (get them at [strava.com/settings/api](https://www.strava.com/settings/api), where the Authorization Callback Domain must be set to `callback` — a bare host with no scheme or slashes, matching the host of the `clubcalendar://callback` redirect URI). Strava allows one API application per account; reuse the same one for macOS and iOS.
2. Tap **Connect to Strava** → Safari sheet opens → sign in → authorize.
3. Pick which clubs to sync.
4. Grant **Full Access** to Calendar when iOS prompts.

Then open the **Calendar** app on the simulator (Home screen → swipe → Calendar). You should see a "Club Calendar" calendar with your events. If you see them on the sim, you'll see them on the phone.

To override the sim model:

```bash
make ios-test IOS_SIM_DEVICE='iPhone 17 Pro'
make ios-run  IOS_SIM_DEVICE='iPhone 17'
```

---

## 3. Install on the iPhone

```bash
make ios-install-device
```

What happens:

1. Generates an iOS Xcode project from `project.yml`.
2. `xcodebuild archive` builds + signs a release archive with your `DEVELOPMENT_TEAM`.
3. `xcrun devicectl install` pushes the `.app` to your iPhone over USB.
4. The app appears on your home screen as **Club Calendar**.

### First-launch step: trust the developer

The phone won't launch a Personal-Team-signed app until you tell it the team is trusted. On the iPhone:

1. **Settings → General → VPN & Device Management.**
2. Under **Developer App**, tap the row showing your Apple ID.
3. Tap **Trust "[your Apple ID]"** → confirm in the popup.
4. Go back to the home screen. Tap Club Calendar — it launches normally.

You only do this once per developer-cert per phone. If you reinstall after the cert expires (see below), the trust persists.

### After-launch: onboarding (same as simulator)

The app opens to the API-credentials step. Same flow:

1. Paste Strava Client ID + Secret. Strava's Authorization Callback Domain must be set to `callback`.
2. Connect to Strava (Safari sheet appears).
3. Pick clubs.
4. Grant **Full Access** to Calendar when iOS prompts.

Events should appear in the Apple Calendar app within seconds.

---

## 4. Free Apple ID limits + workarounds

The free Personal Team has three constraints worth knowing:

### a. Apps expire after 7 days

A Personal-Team-signed app stops launching 7 days after build. Symptom: tap the icon, get "Untrusted Developer" or the icon goes grey. Fix:

```bash
make ios-install-device
```

Re-running `ios-install-device` re-signs with a fresh provisioning profile valid for another 7 days. Your data, keychain tokens, calendar permission, and sync interval all persist across reinstalls — only the binary refreshes.

You can also re-sign weekly by opening the Xcode project and hitting **Cmd-R** with the phone connected. Same effect.

### b. Limited to 3 sideloaded apps at a time

Per Apple ID. Not a problem since we ship one app, but if you sideload other tools (e.g. AltStore, sideloadly games) you may hit the cap and need to delete one.

### c. No TestFlight, no notifications via APNs

Neither matters for personal use. If you ever want either, $99/year unlocks them.

---

## 5. Troubleshooting

### "Could not launch ClubCalendar" / "Untrusted Developer"

You forgot to trust the cert on the phone after install. Settings → General → VPN & Device Management → tap your Apple ID → Trust.

### "No profiles for 'com.clubcalendar.ios' were found"

Xcode hasn't registered the bundle ID with Apple's signing servers yet. Open the project in Xcode, set the team in Signing & Capabilities, wait for the green "Xcode Managed" line, then re-run `make ios-install-device`.

### `xcodebuild archive` hangs at "Resolve Package Graph"

Force-kill and clear the build cache:

```bash
pkill -9 -f xcodebuild
pkill -9 -f SWBBuildService
rm -rf ~/Library/Developer/Xcode/DerivedData/ClubCalendar-iOS-*
make ios-install-device
```

### `xcrun devicectl list devices` shows nothing

Phone isn't trusted. Unplug → replug → unlock the phone → tap Trust when the prompt appears. If no prompt comes up, in iPhone Settings → General → VPN & Device Management → tap any cert and look for a "Trust Computer" entry; or reset Location & Privacy in Settings → General → Transfer or Reset iPhone → Reset → Reset Location & Privacy, then replug to trigger the prompt again.

### The app installed but doesn't sync events

Most likely the Strava Authorization Callback Domain isn't set to `callback` (it must equal the host of the `clubcalendar://callback` redirect URI — a bare `callback`, no scheme or slashes). Open [strava.com/settings/api](https://www.strava.com/settings/api), set it, save. Then in the app: Settings → Disconnect → reconnect.

If OAuth succeeds but no events appear: check Settings → Status → Last synced. If the timestamp updates but no events show, you have no future club events on Strava (the API returns only upcoming). Pick a club you know has scheduled events.

### Background refresh seems unreliable

It is. iOS background refresh is opportunistic — Apple's guidance is "30 sec of execution at a time the system thinks is good". On a personal-use app the system has little prior to learn from. The foreground catch-up sync runs whenever you open the app, so the visible UI is always fresh.

To inspect background runs:

```bash
make ios-logs                    # if a sim is booted, streams its log
```

Or on the phone: connect via USB, open Xcode, **Window → Devices and Simulators → select phone → View Device Logs → filter on `subsystem == com.clubcalendar.app`**.

### How to fully reset

```bash
# On the phone
# 1. Long-press the app icon → Remove App → Delete App
# 2. Settings → Privacy & Security → Calendars → revoke

# On the Mac
rm -rf ~/Library/Developer/Xcode/DerivedData/ClubCalendar-iOS-*
make ios-install-device
```

Tokens, settings, club list — all live in keychain + UserDefaults inside the app sandbox. Deleting the app wipes all of it.

---

## 6. What you cannot do without a paid Apple Developer Program

- Distribute via TestFlight (would let you install on multiple phones without re-signing every 7 days).
- Distribute via the App Store.
- Use push notifications (APNs).
- Use CloudKit (production environment — development environment is free).
- Use `keychain-access-groups` to share keychain items across multiple Personal-Team apps.

For a personal calendar-sync app, none of these matter.

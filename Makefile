.PHONY: help clean \
        macos-build macos-build-debug macos-test macos-test-verbose macos-run macos-dev macos-open \
        macos-open-release macos-logs macos-bundle macos-bundle-debug macos-sign macos-dmg \
        macos-release macos-kill macos-restart macos-setup-cert macos-reset-calendar \
        macos-reset-all macos-open-calendar-settings \
        ios-gen ios-build ios-test ios-test-verbose ios-coverage ios-run ios-clean \
        ios-archive ios-install-device ios-logs

# ============================================================================
# Shared
# ============================================================================

APP_NAME = ClubCalendar

# ============================================================================
# macOS config
# ============================================================================

MACOS_SRC_DIR = ClubCalendar-macOS/Sources
MACOS_BUNDLE_ID = com.clubcalendar.app
MACOS_BUILD_DIR_RELEASE = .build/release
MACOS_BUILD_DIR_DEBUG = .build/debug
MACOS_APP_PATH_RELEASE = $(MACOS_BUILD_DIR_RELEASE)/$(APP_NAME).app
MACOS_APP_PATH_DEBUG = $(MACOS_BUILD_DIR_DEBUG)/$(APP_NAME).app
MACOS_DEV_CERT_NAME = ClubCalendar Development
MACOS_ENTITLEMENTS = $(MACOS_SRC_DIR)/Resources/ClubCalendar.entitlements

# Function to resolve the codesigning identity at runtime
get_sign_identity = $(shell security find-identity -v -p codesigning 2>/dev/null | grep -q "$(MACOS_DEV_CERT_NAME)" && echo '"$(MACOS_DEV_CERT_NAME)"' || echo '-')

# ============================================================================
# iOS config
# ============================================================================

IOS_PROJECT_DIR = ClubCalendar-iOS
IOS_PROJECT = $(IOS_PROJECT_DIR)/ClubCalendar-iOS.xcodeproj
IOS_SCHEME = ClubCalendarIOS
# iOS 26.5 SDK ships iPhone 17-series sims only — closest match to your
# iPhone 16 Pro Max is iPhone 17 Pro Max (same screen geometry).
# Override via `make ios-test IOS_SIM_DEVICE='iPhone 17 Pro'` if you prefer.
IOS_SIM_DEVICE ?= iPhone 17 Pro Max
IOS_SIM_DESTINATION = platform=iOS Simulator,name=$(IOS_SIM_DEVICE)
IOS_DEVICE_DESTINATION ?= generic/platform=iOS
IOS_ARCHIVE_PATH = .build/ios/ClubCalendar.xcarchive
IOS_BUNDLE_ID = com.clubcalendar.ios
# Ad-hoc sign simulator builds (identity "-") so the app gets its
# keychain-access-groups entitlement. Unsigned builds (CODE_SIGNING_ALLOWED=NO)
# hit -34018 (errSecMissingEntitlement) the moment they touch the keychain. No
# Apple Developer team or provisioning profile is needed for the simulator.
IOS_SIM_SIGNING = CODE_SIGN_STYLE=Manual CODE_SIGN_IDENTITY="-" \
	CODE_SIGNING_REQUIRED=YES CODE_SIGNING_ALLOWED=YES \
	PROVISIONING_PROFILE_SPECIFIER=""

# ============================================================================
# macOS targets
# ============================================================================

# Build release binary
macos-build:
	swift build -c release

# Build debug binary (faster compilation)
macos-build-debug:
	swift build -c debug

# Run SPM tests (ClubCalendarMac + ClubCalendarCore via ClubCalendarMacTests)
macos-test:
	swift test

# Run tests with verbose output
macos-test-verbose:
	swift test --verbose

# Run the app directly (limited - no URL scheme or calendar access)
macos-run:
	swift run

# Development: build debug, bundle, sign, and open
macos-dev: macos-bundle-debug
	@echo "Opening macOS app..."
	@open "$(MACOS_APP_PATH_DEBUG)"

# Open the debug app (assumes already built)
macos-open:
	@open "$(MACOS_APP_PATH_DEBUG)"

# Open release app
macos-open-release:
	@open "$(MACOS_APP_PATH_RELEASE)"

# Stream macOS app logs from Console
macos-logs:
	@echo "Showing ClubCalendar macOS logs (Ctrl+C to stop)..."
	@log stream --predicate 'subsystem == "com.clubcalendar.app" OR process == "ClubCalendar"' --level debug

# Create debug app bundle
macos-bundle-debug: macos-build-debug macos-setup-cert
	@echo "Creating debug app bundle..."
	@mkdir -p "$(MACOS_APP_PATH_DEBUG)/Contents/MacOS"
	@mkdir -p "$(MACOS_APP_PATH_DEBUG)/Contents/Resources"
	@cp "$(MACOS_BUILD_DIR_DEBUG)/$(APP_NAME)" "$(MACOS_APP_PATH_DEBUG)/Contents/MacOS/"
	@cp "$(MACOS_SRC_DIR)/Resources/AppIcon.icns" "$(MACOS_APP_PATH_DEBUG)/Contents/Resources/"
	@cp "$(MACOS_SRC_DIR)/Resources/icon_menubarTemplate.png" "$(MACOS_APP_PATH_DEBUG)/Contents/Resources/"
	@cp "$(MACOS_SRC_DIR)/Resources/icon_menubarTemplate@2x.png" "$(MACOS_APP_PATH_DEBUG)/Contents/Resources/"
	@$(call create_plist,$(MACOS_APP_PATH_DEBUG))
	@echo "Signing app with identity: $(call get_sign_identity)"
	@codesign --force --deep --sign $(call get_sign_identity) --entitlements $(MACOS_ENTITLEMENTS) "$(MACOS_APP_PATH_DEBUG)"
	@echo "Debug app ready at $(MACOS_APP_PATH_DEBUG)"

# Create release app bundle
macos-bundle: macos-build
	@echo "Creating macOS app bundle..."
	@mkdir -p "$(MACOS_APP_PATH_RELEASE)/Contents/MacOS"
	@mkdir -p "$(MACOS_APP_PATH_RELEASE)/Contents/Resources"
	@cp "$(MACOS_BUILD_DIR_RELEASE)/$(APP_NAME)" "$(MACOS_APP_PATH_RELEASE)/Contents/MacOS/"
	@cp "$(MACOS_SRC_DIR)/Resources/AppIcon.icns" "$(MACOS_APP_PATH_RELEASE)/Contents/Resources/"
	@cp "$(MACOS_SRC_DIR)/Resources/icon_menubarTemplate.png" "$(MACOS_APP_PATH_RELEASE)/Contents/Resources/"
	@cp "$(MACOS_SRC_DIR)/Resources/icon_menubarTemplate@2x.png" "$(MACOS_APP_PATH_RELEASE)/Contents/Resources/"
	@$(call create_plist,$(MACOS_APP_PATH_RELEASE))
	@echo "App bundle created at $(MACOS_APP_PATH_RELEASE)"

# Sign the release app (ensures dev certificate exists)
macos-sign: macos-bundle macos-setup-cert
	@echo "Signing app with identity: $(call get_sign_identity)"
	codesign --force --deep --sign $(call get_sign_identity) --entitlements $(MACOS_ENTITLEMENTS) "$(MACOS_APP_PATH_RELEASE)"
	@echo "App signed successfully"

# Create DMG installer with an /Applications shortcut for drag-install
DMG_STAGING = .build/dmg-staging
macos-dmg: macos-sign
	@echo "Creating DMG..."
	@rm -f $(APP_NAME).dmg
	@rm -rf "$(DMG_STAGING)"
	@mkdir -p "$(DMG_STAGING)"
	@cp -R "$(MACOS_APP_PATH_RELEASE)" "$(DMG_STAGING)/"
	@ln -s /Applications "$(DMG_STAGING)/Applications"
	hdiutil create -volname "$(APP_NAME)" -srcfolder "$(DMG_STAGING)" -ov -format UDZO "$(APP_NAME).dmg"
	@rm -rf "$(DMG_STAGING)"
	@echo "DMG created: $(APP_NAME).dmg"
	open $(CURDIR)/$(APP_NAME).dmg

# Full macOS release build
macos-release: clean macos-dmg
	@echo "macOS release build complete!"

# Kill running instances of the macOS app
macos-kill:
	@pkill -x $(APP_NAME) 2>/dev/null || true
	@echo "Killed any running $(APP_NAME) instances"

# Restart: kill, rebuild, and reopen
macos-restart: macos-kill macos-dev

# Create local development certificate (one-time setup)
macos-setup-cert:
	@./scripts/create-dev-cert.sh

# Reset macOS calendar permission (requires re-grant on next launch)
macos-reset-calendar:
	@tccutil reset Calendar $(MACOS_BUNDLE_ID)
	@echo "Calendar permission reset. Run 'make macos-restart' to relaunch."

# Reset all macOS permissions (calendar, keychain items)
macos-reset-all: macos-reset-calendar
	@security delete-generic-password -a "com.clubcalendar.clientId" 2>/dev/null || true
	@security delete-generic-password -a "com.clubcalendar.clientSecret" 2>/dev/null || true
	@security delete-generic-password -a "com.clubcalendar.accessToken" 2>/dev/null || true
	@security delete-generic-password -a "com.clubcalendar.refreshToken" 2>/dev/null || true
	@security delete-generic-password -a "com.clubcalendar.tokenExpiry" 2>/dev/null || true
	@security delete-generic-password -a "com.clubcalendar.athleteId" 2>/dev/null || true
	@security delete-generic-password -a "com.clubcalendar.athleteName" 2>/dev/null || true
	@echo "All permissions and keychain items reset."

# Open System Settings to calendar permissions
macos-open-calendar-settings:
	@open "x-apple.systempreferences:com.apple.preference.security?Privacy_Calendars"

# Helper function to create Info.plist for the macOS bundle
define create_plist
	@echo '<?xml version="1.0" encoding="UTF-8"?>' > "$(1)/Contents/Info.plist"
	@echo '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">' >> "$(1)/Contents/Info.plist"
	@echo '<plist version="1.0">' >> "$(1)/Contents/Info.plist"
	@echo '<dict>' >> "$(1)/Contents/Info.plist"
	@echo '    <key>CFBundleExecutable</key>' >> "$(1)/Contents/Info.plist"
	@echo '    <string>$(APP_NAME)</string>' >> "$(1)/Contents/Info.plist"
	@echo '    <key>CFBundleIdentifier</key>' >> "$(1)/Contents/Info.plist"
	@echo '    <string>$(MACOS_BUNDLE_ID)</string>' >> "$(1)/Contents/Info.plist"
	@echo '    <key>CFBundleName</key>' >> "$(1)/Contents/Info.plist"
	@echo '    <string>$(APP_NAME)</string>' >> "$(1)/Contents/Info.plist"
	@echo '    <key>CFBundleDisplayName</key>' >> "$(1)/Contents/Info.plist"
	@echo '    <string>Club Calendar</string>' >> "$(1)/Contents/Info.plist"
	@echo '    <key>CFBundleVersion</key>' >> "$(1)/Contents/Info.plist"
	@echo '    <string>1.0.0</string>' >> "$(1)/Contents/Info.plist"
	@echo '    <key>CFBundleShortVersionString</key>' >> "$(1)/Contents/Info.plist"
	@echo '    <string>1.0.0</string>' >> "$(1)/Contents/Info.plist"
	@echo '    <key>CFBundlePackageType</key>' >> "$(1)/Contents/Info.plist"
	@echo '    <string>APPL</string>' >> "$(1)/Contents/Info.plist"
	@echo '    <key>CFBundleIconFile</key>' >> "$(1)/Contents/Info.plist"
	@echo '    <string>AppIcon</string>' >> "$(1)/Contents/Info.plist"
	@echo '    <key>LSMinimumSystemVersion</key>' >> "$(1)/Contents/Info.plist"
	@echo '    <string>26.0</string>' >> "$(1)/Contents/Info.plist"
	@echo '    <key>LSUIElement</key>' >> "$(1)/Contents/Info.plist"
	@echo '    <true/>' >> "$(1)/Contents/Info.plist"
	@echo '    <key>CFBundleURLTypes</key>' >> "$(1)/Contents/Info.plist"
	@echo '    <array>' >> "$(1)/Contents/Info.plist"
	@echo '        <dict>' >> "$(1)/Contents/Info.plist"
	@echo '            <key>CFBundleURLName</key>' >> "$(1)/Contents/Info.plist"
	@echo '            <string>$(MACOS_BUNDLE_ID)</string>' >> "$(1)/Contents/Info.plist"
	@echo '            <key>CFBundleURLSchemes</key>' >> "$(1)/Contents/Info.plist"
	@echo '            <array>' >> "$(1)/Contents/Info.plist"
	@echo '                <string>clubcalendar</string>' >> "$(1)/Contents/Info.plist"
	@echo '            </array>' >> "$(1)/Contents/Info.plist"
	@echo '        </dict>' >> "$(1)/Contents/Info.plist"
	@echo '    </array>' >> "$(1)/Contents/Info.plist"
	@echo '    <key>NSCalendarsUsageDescription</key>' >> "$(1)/Contents/Info.plist"
	@echo '    <string>Club Calendar needs access to your calendars to sync Strava club events.</string>' >> "$(1)/Contents/Info.plist"
	@echo '    <key>NSCalendarsFullAccessUsageDescription</key>' >> "$(1)/Contents/Info.plist"
	@echo '    <string>Club Calendar needs full access to your calendars to create and update Strava club events.</string>' >> "$(1)/Contents/Info.plist"
	@echo '</dict>' >> "$(1)/Contents/Info.plist"
	@echo '</plist>' >> "$(1)/Contents/Info.plist"
endef

# ============================================================================
# iOS targets
# ============================================================================

# Regenerate the iOS Xcode project from project.yml (idempotent)
ios-gen:
	@cd $(IOS_PROJECT_DIR) && xcodegen generate

# Build iOS debug for the default simulator
ios-build: ios-gen
	@xcodebuild build \
		-project $(IOS_PROJECT) \
		-scheme $(IOS_SCHEME) \
		-destination '$(IOS_SIM_DESTINATION)' \
		$(IOS_SIM_SIGNING)

# Run the iOS unit-test bundle on the default simulator. We pre-grant
# Calendar permission so `requestFullAccessToEvents()` returns granted
# without popping a UI prompt that would wedge the test runner, and so the
# real-EventKit integration tests in CalendarServiceIntegrationTests can
# actually write to the store.
ios-test: ios-gen
	@DEVICE_ID=$$(xcrun simctl list devices available | grep -E "$(IOS_SIM_DEVICE) \(" | head -1 | sed -E 's/.*\(([A-F0-9-]+)\).*/\1/'); \
	if [ -z "$$DEVICE_ID" ]; then echo "Simulator '$(IOS_SIM_DEVICE)' not found"; exit 1; fi; \
	xcrun simctl boot $$DEVICE_ID 2>/dev/null || true; \
	xcrun simctl privacy $$DEVICE_ID grant calendar $(IOS_BUNDLE_ID); \
	xcodebuild test \
		-project $(IOS_PROJECT) \
		-scheme $(IOS_SCHEME) \
		-destination "platform=iOS Simulator,id=$$DEVICE_ID" \
		-enableCodeCoverage YES \
		$(IOS_SIM_SIGNING)

# Verbose iOS tests (full xcodebuild output)
ios-test-verbose: ios-gen
	@xcodebuild test \
		-project $(IOS_PROJECT) \
		-scheme $(IOS_SCHEME) \
		-destination '$(IOS_SIM_DESTINATION)' \
		-enableCodeCoverage YES \
		$(IOS_SIM_SIGNING)

# Print line-by-line coverage of the iOS target after `ios-test`
ios-coverage: ios-test
	@RESULT=$$(find ~/Library/Developer/Xcode/DerivedData -name '*.xcresult' -path '*ClubCalendar-iOS*' -print0 2>/dev/null | xargs -0 ls -t 2>/dev/null | head -1); \
	if [ -z "$$RESULT" ]; then echo "No xcresult bundle found — run 'make ios-test' first."; exit 1; fi; \
	xcrun xccov view --report --only-targets "$$RESULT"

# Boot the iPhone simulator and install/launch the debug app
ios-run: ios-build
	@DEVICE_ID=$$(xcrun simctl list devices available | grep -E "$(IOS_SIM_DEVICE) \(" | head -1 | sed -E 's/.*\(([A-F0-9-]+)\).*/\1/'); \
	if [ -z "$$DEVICE_ID" ]; then echo "Simulator '$(IOS_SIM_DEVICE)' not found"; exit 1; fi; \
	xcrun simctl boot $$DEVICE_ID 2>/dev/null || true; \
	open -a Simulator; \
	APP=$$(find ~/Library/Developer/Xcode/DerivedData -name 'ClubCalendar.app' -path '*iphonesimulator*' -print0 2>/dev/null | xargs -0 ls -td 2>/dev/null | head -1); \
	xcrun simctl install $$DEVICE_ID "$$APP"; \
	xcrun simctl launch $$DEVICE_ID $(IOS_BUNDLE_ID)

# Wipe iOS build artifacts (DerivedData lives outside the repo so we only
# delete what we put in .build)
ios-clean:
	@rm -rf .build/ios
	@xcodebuild clean -project $(IOS_PROJECT) -scheme $(IOS_SCHEME) 2>/dev/null || true

# Stream iOS app logs from the booted simulator (subsystem filter)
ios-logs:
	@echo "Streaming Club Calendar iOS logs from the booted simulator..."
	@DEVICE_ID=$$(xcrun simctl list devices | grep -i booted | head -1 | sed -E 's/.*\(([A-F0-9-]+)\).*/\1/'); \
	if [ -z "$$DEVICE_ID" ]; then echo "No booted simulator. Run 'make ios-run' first."; exit 1; fi; \
	xcrun simctl spawn $$DEVICE_ID log stream --predicate 'subsystem == "com.clubcalendar.app"' --level debug

# Build a signed .xcarchive for installing on a physical iPhone via Xcode.
# Requires DEVELOPMENT_TEAM=YOURTEAMID on the command line, or signing
# configured in Xcode (open the project once, set your team).
ios-archive: ios-gen
	@if [ -z "$$DEVELOPMENT_TEAM" ]; then \
		echo "ERROR: pass DEVELOPMENT_TEAM=<your 10-char team ID>."; \
		echo "       Find it at developer.apple.com/account → Membership."; \
		exit 1; \
	fi
	@mkdir -p .build/ios
	@xcodebuild archive \
		-project $(IOS_PROJECT) \
		-scheme $(IOS_SCHEME) \
		-destination '$(IOS_DEVICE_DESTINATION)' \
		-archivePath $(IOS_ARCHIVE_PATH) \
		DEVELOPMENT_TEAM=$$DEVELOPMENT_TEAM \
		CODE_SIGN_STYLE=Automatic

# Install the archived app on a connected iPhone using devicectl.
# Requires `xcrun devicectl` (Xcode 15+) and a connected/paired iPhone.
ios-install-device: ios-archive
	@DEVICE_ID=$$(xcrun devicectl list devices 2>/dev/null | awk '/^[A-F0-9-]+ +.*iPhone/ {print $$1; exit}'); \
	if [ -z "$$DEVICE_ID" ]; then echo "No iPhone connected. Plug yours in and trust this Mac."; exit 1; fi; \
	APP=$$(find $(IOS_ARCHIVE_PATH)/Products/Applications -maxdepth 1 -name '*.app' | head -1); \
	xcrun devicectl device install app --device $$DEVICE_ID "$$APP"

# ============================================================================
# Shared
# ============================================================================

# Clean build artifacts (both platforms)
clean:
	swift package clean
	rm -rf .build
	rm -rf $(APP_NAME).dmg
	@xcodebuild clean -project $(IOS_PROJECT) -scheme $(IOS_SCHEME) 2>/dev/null || true

# Help
help:
	@echo "Club Calendar — Development Commands"
	@echo ""
	@echo "macOS — develop:"
	@echo "  make macos-dev               Build debug, bundle, sign, and open the menu-bar app"
	@echo "  make macos-restart           Kill running app, rebuild, and reopen"
	@echo "  make macos-open              Open the debug app (assumes already built)"
	@echo "  make macos-kill              Kill running instances of the app"
	@echo "  make macos-logs              Stream macOS app logs from Console"
	@echo ""
	@echo "macOS — build / test:"
	@echo "  make macos-build             Build release binary via SPM"
	@echo "  make macos-build-debug       Build debug binary via SPM"
	@echo "  make macos-test              Run all SPM tests (Mac + Core)"
	@echo "  make macos-test-verbose      Run tests with verbose output"
	@echo "  make macos-bundle            Create release .app bundle"
	@echo "  make macos-bundle-debug      Create debug .app bundle"
	@echo ""
	@echo "macOS — release:"
	@echo "  make macos-sign              Build and sign release app (ad-hoc)"
	@echo "  make macos-dmg               Create signed DMG installer"
	@echo "  make macos-release           Clean + build + DMG"
	@echo ""
	@echo "macOS — setup / reset:"
	@echo "  make macos-setup-cert        Create local dev cert (fixes keychain prompts)"
	@echo "  make macos-reset-calendar    Reset calendar permission"
	@echo "  make macos-reset-all         Reset all permissions and keychain items"
	@echo "  make macos-open-calendar-settings  Open System Settings → Calendars"
	@echo ""
	@echo "iOS (override sim via IOS_SIM_DEVICE='iPhone 17 Pro'):"
	@echo "  make ios-gen                 Regenerate Xcode project from project.yml"
	@echo "  make ios-build               Build iOS debug for simulator"
	@echo "  make ios-test                Run iOS unit tests with coverage"
	@echo "  make ios-coverage            Print iOS coverage report (runs ios-test first)"
	@echo "  make ios-run                 Build + boot simulator + install + launch"
	@echo "  make ios-logs                Stream iOS app logs from booted simulator"
	@echo "  make ios-archive             Build signed archive (set DEVELOPMENT_TEAM=...)"
	@echo "  make ios-install-device      Install archived app on connected iPhone"
	@echo "  make ios-clean               Remove iOS build artifacts"
	@echo ""
	@echo "Shared:"
	@echo "  make clean                   Remove all build artifacts (macOS + iOS)"
	@echo "  make help                    Show this help"

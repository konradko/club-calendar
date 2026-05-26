.PHONY: build build-debug test run dev open clean sign dmg release logs setup-cert

APP_NAME = ClubCalendar
BUILD_DIR_RELEASE = .build/release
BUILD_DIR_DEBUG = .build/debug
APP_PATH_RELEASE = $(BUILD_DIR_RELEASE)/$(APP_NAME).app
APP_PATH_DEBUG = $(BUILD_DIR_DEBUG)/$(APP_NAME).app
BUNDLE_ID = com.clubcalendar.app
DEV_CERT_NAME = ClubCalendar Development
ENTITLEMENTS = ClubCalendar/Resources/ClubCalendar.entitlements

# Function to get sign identity (evaluated at runtime)
get_sign_identity = $(shell security find-identity -v -p codesigning 2>/dev/null | grep -q "$(DEV_CERT_NAME)" && echo '"$(DEV_CERT_NAME)"' || echo '-')

# Build release binary
build:
	swift build -c release

# Build debug binary (faster compilation)
build-debug:
	swift build -c debug

# Run tests
test:
	swift test

# Run tests with verbose output
test-verbose:
	swift test --verbose

# Run the app directly (limited - no URL scheme or calendar access)
run:
	swift run

# Development: build debug, bundle, sign, and open
dev: bundle-debug
	@echo "Opening app..."
	@open "$(APP_PATH_DEBUG)"

# Open the debug app (assumes already built)
open:
	@open "$(APP_PATH_DEBUG)"

# Open release app
open-release:
	@open "$(APP_PATH_RELEASE)"

# Show app logs from Console
logs:
	@echo "Showing ClubCalendar logs (Ctrl+C to stop)..."
	@log stream --predicate 'subsystem == "com.clubcalendar.app" OR process == "ClubCalendar"' --level debug

# Clean build artifacts
clean:
	swift package clean
	rm -rf .build
	rm -rf $(APP_NAME).dmg

# Create debug app bundle
bundle-debug: build-debug setup-cert
	@echo "Creating debug app bundle..."
	@mkdir -p "$(APP_PATH_DEBUG)/Contents/MacOS"
	@mkdir -p "$(APP_PATH_DEBUG)/Contents/Resources"
	@cp "$(BUILD_DIR_DEBUG)/$(APP_NAME)" "$(APP_PATH_DEBUG)/Contents/MacOS/"
	@cp "ClubCalendar/Resources/AppIcon.icns" "$(APP_PATH_DEBUG)/Contents/Resources/"
	@cp "ClubCalendar/Resources/icon_menubarTemplate.png" "$(APP_PATH_DEBUG)/Contents/Resources/"
	@cp "ClubCalendar/Resources/icon_menubarTemplate@2x.png" "$(APP_PATH_DEBUG)/Contents/Resources/"
	@$(call create_plist,$(APP_PATH_DEBUG))
	@echo "Signing app with identity: $(call get_sign_identity)"
	@codesign --force --deep --sign $(call get_sign_identity) --entitlements $(ENTITLEMENTS) "$(APP_PATH_DEBUG)"
	@echo "Debug app ready at $(APP_PATH_DEBUG)"

# Create release app bundle
bundle: build
	@echo "Creating app bundle..."
	@mkdir -p "$(APP_PATH_RELEASE)/Contents/MacOS"
	@mkdir -p "$(APP_PATH_RELEASE)/Contents/Resources"
	@cp "$(BUILD_DIR_RELEASE)/$(APP_NAME)" "$(APP_PATH_RELEASE)/Contents/MacOS/"
	@cp "ClubCalendar/Resources/AppIcon.icns" "$(APP_PATH_RELEASE)/Contents/Resources/"
	@cp "ClubCalendar/Resources/icon_menubarTemplate.png" "$(APP_PATH_RELEASE)/Contents/Resources/"
	@cp "ClubCalendar/Resources/icon_menubarTemplate@2x.png" "$(APP_PATH_RELEASE)/Contents/Resources/"
	@$(call create_plist,$(APP_PATH_RELEASE))
	@echo "App bundle created at $(APP_PATH_RELEASE)"

# Sign the release app (ensures dev certificate exists)
sign: bundle setup-cert
	@echo "Signing app with identity: $(call get_sign_identity)"
	codesign --force --deep --sign $(call get_sign_identity) --entitlements $(ENTITLEMENTS) "$(APP_PATH_RELEASE)"
	@echo "App signed successfully"

# Create DMG installer with an /Applications shortcut for drag-install
DMG_STAGING = .build/dmg-staging
dmg: sign
	@echo "Creating DMG..."
	@rm -f $(APP_NAME).dmg
	@rm -rf "$(DMG_STAGING)"
	@mkdir -p "$(DMG_STAGING)"
	@cp -R "$(APP_PATH_RELEASE)" "$(DMG_STAGING)/"
	@ln -s /Applications "$(DMG_STAGING)/Applications"
	hdiutil create -volname "$(APP_NAME)" -srcfolder "$(DMG_STAGING)" -ov -format UDZO "$(APP_NAME).dmg"
	@rm -rf "$(DMG_STAGING)"
	@echo "DMG created: $(APP_NAME).dmg"
	open /Users/konrad/workspace/club-calendar/ClubCalendar.dmg

# Full release build
release: clean dmg
	@echo "Release build complete!"

# Kill running instances of the app
kill:
	@pkill -x $(APP_NAME) 2>/dev/null || true
	@echo "Killed any running $(APP_NAME) instances"

# Restart: kill, rebuild, and reopen
restart: kill dev

# Helper function to create Info.plist
define create_plist
	@echo '<?xml version="1.0" encoding="UTF-8"?>' > "$(1)/Contents/Info.plist"
	@echo '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">' >> "$(1)/Contents/Info.plist"
	@echo '<plist version="1.0">' >> "$(1)/Contents/Info.plist"
	@echo '<dict>' >> "$(1)/Contents/Info.plist"
	@echo '    <key>CFBundleExecutable</key>' >> "$(1)/Contents/Info.plist"
	@echo '    <string>$(APP_NAME)</string>' >> "$(1)/Contents/Info.plist"
	@echo '    <key>CFBundleIdentifier</key>' >> "$(1)/Contents/Info.plist"
	@echo '    <string>$(BUNDLE_ID)</string>' >> "$(1)/Contents/Info.plist"
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
	@echo '            <string>$(BUNDLE_ID)</string>' >> "$(1)/Contents/Info.plist"
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

# Create local development certificate (one-time setup)
setup-cert:
	@./scripts/create-dev-cert.sh

# Reset calendar permission (requires re-grant on next launch)
reset-calendar:
	@tccutil reset Calendar $(BUNDLE_ID)
	@echo "Calendar permission reset. Run 'make restart' to relaunch."

# Reset all permissions (calendar, keychain items)
reset-all: reset-calendar
	@security delete-generic-password -a "com.clubcalendar.clientId" 2>/dev/null || true
	@security delete-generic-password -a "com.clubcalendar.clientSecret" 2>/dev/null || true
	@security delete-generic-password -a "com.clubcalendar.accessToken" 2>/dev/null || true
	@security delete-generic-password -a "com.clubcalendar.refreshToken" 2>/dev/null || true
	@security delete-generic-password -a "com.clubcalendar.tokenExpiry" 2>/dev/null || true
	@security delete-generic-password -a "com.clubcalendar.athleteId" 2>/dev/null || true
	@security delete-generic-password -a "com.clubcalendar.athleteName" 2>/dev/null || true
	@echo "All permissions and keychain items reset."

# Open System Settings to calendar permissions
open-calendar-settings:
	@open "x-apple.systempreferences:com.apple.preference.security?Privacy_Calendars"

# Help
help:
	@echo "Club Calendar - Development Commands"
	@echo ""
	@echo "Development:"
	@echo "  make dev        - Build debug, bundle, sign, and open the app"
	@echo "  make restart    - Kill running app, rebuild, and reopen"
	@echo "  make open       - Open the debug app (assumes already built)"
	@echo "  make kill       - Kill running instances of the app"
	@echo "  make logs       - Stream app logs from Console"
	@echo ""
	@echo "Building:"
	@echo "  make build      - Build release binary"
	@echo "  make build-debug - Build debug binary (faster)"
	@echo "  make bundle     - Create release app bundle"
	@echo "  make bundle-debug - Create debug app bundle"
	@echo ""
	@echo "Testing:"
	@echo "  make test       - Run all tests"
	@echo "  make test-verbose - Run tests with verbose output"
	@echo ""
	@echo "Release:"
	@echo "  make sign       - Build and sign release app (ad-hoc)"
	@echo "  make dmg        - Create DMG installer"
	@echo "  make release    - Clean build and create DMG"
	@echo ""
	@echo "Setup & Reset:"
	@echo "  make setup-cert          - Create local dev certificate (fixes keychain prompts)"
	@echo "  make reset-calendar      - Reset calendar permission"
	@echo "  make reset-all           - Reset all permissions and keychain items"
	@echo "  make open-calendar-settings - Open System Settings to calendar permissions"
	@echo ""
	@echo "Other:"
	@echo "  make clean      - Remove build artifacts"
	@echo "  make help       - Show this help"

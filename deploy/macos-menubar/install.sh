#!/bin/bash
# Install Club Calendar menu bar app with optional startup
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PLIST_NAME="com.club-calendar.menubar.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --startup     Install and enable startup at login"
    echo "  --no-startup  Install without startup (default)"
    echo "  --uninstall   Remove startup agent"
    echo "  --status      Show current status"
    echo ""
    echo "After install, run manually with:"
    echo "  club-calendar-menubar"
}

install_deps() {
    echo "Installing dependencies..."
    cd "$PROJECT_ROOT"
    uv sync --extra menubar

    # Create output directory
    mkdir -p "$HOME/.club-calendar"
}

install_startup() {
    echo "Installing startup agent..."

    mkdir -p "$LAUNCH_AGENTS_DIR"

    # Get paths
    local venv_path="$PROJECT_ROOT/.venv"
    local home_path="$HOME"

    # Create plist from template
    sed -e "s|__VENV_PATH__|$venv_path|g" \
        -e "s|__PROJECT_PATH__|$PROJECT_ROOT|g" \
        -e "s|__HOME__|$home_path|g" \
        "$SCRIPT_DIR/$PLIST_NAME" > "$LAUNCH_AGENTS_DIR/$PLIST_NAME"

    # Load the agent
    launchctl unload "$LAUNCH_AGENTS_DIR/$PLIST_NAME" 2>/dev/null || true
    launchctl load "$LAUNCH_AGENTS_DIR/$PLIST_NAME"

    echo ""
    echo "Menu bar app installed and will start at login."
    echo "Starting now..."
    launchctl start com.club-calendar.menubar
}

uninstall_startup() {
    echo "Removing startup agent..."

    if [ -f "$LAUNCH_AGENTS_DIR/$PLIST_NAME" ]; then
        launchctl unload "$LAUNCH_AGENTS_DIR/$PLIST_NAME" 2>/dev/null || true
        rm "$LAUNCH_AGENTS_DIR/$PLIST_NAME"
        echo "Startup agent removed."
    else
        echo "No startup agent found."
    fi
}

show_status() {
    echo "Club Calendar Menu Bar Status"
    echo "=============================="
    echo ""

    if [ -f "$LAUNCH_AGENTS_DIR/$PLIST_NAME" ]; then
        echo "Startup: Enabled"
        if launchctl list | grep -q "com.club-calendar.menubar"; then
            echo "Running: Yes"
        else
            echo "Running: No"
        fi
    else
        echo "Startup: Not installed"
    fi

    echo ""
    echo "Project: $PROJECT_ROOT"
    echo "Logs: ~/.club-calendar/menubar.log"
}

# Parse arguments
ACTION="install"
STARTUP=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --startup)
            STARTUP=true
            shift
            ;;
        --no-startup)
            STARTUP=false
            shift
            ;;
        --uninstall)
            ACTION="uninstall"
            shift
            ;;
        --status)
            ACTION="status"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Execute
case $ACTION in
    install)
        install_deps
        if [ "$STARTUP" = true ]; then
            install_startup
        else
            echo ""
            echo "Installation complete."
            echo ""
            echo "Run manually:"
            echo "  cd $PROJECT_ROOT && uv run club-calendar-menubar"
            echo ""
            echo "Enable startup at login:"
            echo "  $0 --startup"
        fi
        ;;
    uninstall)
        uninstall_startup
        ;;
    status)
        show_status
        ;;
esac

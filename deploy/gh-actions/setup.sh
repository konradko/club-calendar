#!/usr/bin/env bash
# Setup script for Club Calendar GitHub Actions deployment
# Configures GitHub repository secrets, variables, and Pages

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "📅 Club Calendar GitHub Actions Setup"
echo "======================================"

# Check for gh CLI
if ! command -v gh &> /dev/null; then
    echo -e "${RED}Error: GitHub CLI (gh) is not installed${NC}"
    echo "Install it from: https://cli.github.com/"
    exit 1
fi

# Check gh auth status
if ! gh auth status &> /dev/null; then
    echo -e "${RED}Error: Not authenticated with GitHub CLI${NC}"
    echo "Run: gh auth login"
    exit 1
fi

# Load .env file
ENV_FILE="${1:-.env}"
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}Error: $ENV_FILE not found${NC}"
    echo "Create a .env file with your Strava credentials:"
    echo ""
    echo "  STRAVA_CLIENT_ID=your_client_id"
    echo "  STRAVA_CLIENT_SECRET=your_client_secret"
    echo "  STRAVA_REFRESH_TOKEN=your_refresh_token"
    echo "  STRAVA_CLUB_IDS=123,456,789"
    echo ""
    exit 1
fi

echo "Loading environment from: $ENV_FILE"
set -a
source "$ENV_FILE"
set +a

# Validate required variables
MISSING=""
[ -z "$STRAVA_CLIENT_ID" ] && MISSING="$MISSING STRAVA_CLIENT_ID"
[ -z "$STRAVA_CLIENT_SECRET" ] && MISSING="$MISSING STRAVA_CLIENT_SECRET"
[ -z "$STRAVA_REFRESH_TOKEN" ] && MISSING="$MISSING STRAVA_REFRESH_TOKEN"

if [ -n "$MISSING" ]; then
    echo -e "${RED}Error: Missing required variables:${NC}$MISSING"
    echo "Edit your .env file and fill in these values"
    exit 1
fi

if [ -z "$STRAVA_CLUB_IDS" ]; then
    echo -e "${RED}Error: STRAVA_CLUB_IDS is required${NC}"
    echo "Add club IDs (comma-separated) to your .env file"
    exit 1
fi

echo ""
echo "Setting GitHub secrets..."

# Set secrets (sensitive values)
gh secret set STRAVA_CLIENT_ID --body "$STRAVA_CLIENT_ID"
echo -e "  ${GREEN}✓${NC} STRAVA_CLIENT_ID"

gh secret set STRAVA_CLIENT_SECRET --body "$STRAVA_CLIENT_SECRET"
echo -e "  ${GREEN}✓${NC} STRAVA_CLIENT_SECRET"

gh secret set STRAVA_REFRESH_TOKEN --body "$STRAVA_REFRESH_TOKEN"
echo -e "  ${GREEN}✓${NC} STRAVA_REFRESH_TOKEN"

# Generate CALENDAR_ID if not set (UUID without dashes)
if [ -z "$CALENDAR_ID" ]; then
    CALENDAR_ID=$(uuidgen 2>/dev/null || cat /proc/sys/kernel/random/uuid | tr -d '-')
    CALENDAR_ID=${CALENDAR_ID//-/}
    echo "CALENDAR_ID=$CALENDAR_ID" >> "$ENV_FILE"
    echo -e "  ${GREEN}✓${NC} Generated CALENDAR_ID"
fi

echo ""
echo "Setting GitHub variables..."

# Set variables (non-sensitive values)
gh variable set STRAVA_CLUB_IDS --body "$STRAVA_CLUB_IDS"
echo -e "  ${GREEN}✓${NC} STRAVA_CLUB_IDS = $STRAVA_CLUB_IDS"

gh variable set CALENDAR_ID --body "$CALENDAR_ID"
echo -e "  ${GREEN}✓${NC} CALENDAR_ID"

if [ -n "$CLUB_CITY_FILTER" ]; then
    gh variable set CLUB_CITY_FILTER --body "$CLUB_CITY_FILTER"
    echo -e "  ${GREEN}✓${NC} CLUB_CITY_FILTER = $CLUB_CITY_FILTER"
fi

echo ""
echo "Setting up GitHub Pages..."

# Enable GitHub Pages with GitHub Actions as source
gh api repos/{owner}/{repo}/pages -X POST \
    -f "build_type=workflow" 2>/dev/null && \
    echo -e "  ${GREEN}✓${NC} GitHub Pages enabled (workflow deployment)" || \
gh api repos/{owner}/{repo}/pages -X PUT \
    -f "build_type=workflow" 2>/dev/null && \
    echo -e "  ${GREEN}✓${NC} GitHub Pages updated" || \
echo -e "  ${YELLOW}!${NC} GitHub Pages may already be configured (enable via Settings > Pages > Source: GitHub Actions)"

echo ""
echo "Triggering sync workflow..."

if gh workflow run sync.yml 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} Workflow triggered"
    echo ""
    echo -e "${YELLOW}Waiting for workflow to start...${NC}"
    sleep 5
    gh run watch --exit-status || true
else
    echo -e "  ${YELLOW}!${NC} Could not trigger workflow (may need to push first)"
fi

echo ""
echo "======================================"
echo -e "${GREEN}Setup complete!${NC}"
echo ""

# Get calendar URL
OWNER=$(gh repo view --json owner -q .owner.login)
REPO=$(gh repo view --json name -q .name)
echo "Your calendar URL:"
echo -e "  ${GREEN}https://${OWNER}.github.io/${REPO}/club-calendar-${CALENDAR_ID}.ics${NC}"
echo ""
echo "Add this URL to your calendar app:"
echo "  - Google Calendar: Other calendars > From URL"
echo "  - Apple Calendar: File > New Calendar Subscription"
echo "  - Outlook: Add calendar > From web"

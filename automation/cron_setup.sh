#!/usr/bin/env bash
# ==============================================================================
# ServerWatch - Linux Crontab Automated Task Installer & Manager
# Script: cron_setup.sh
# Purpose: Configure, verify, and remove automated cron jobs for health checks,
#          disk monitoring, service audits, log maintenance, and daily reports.
# Target OS: Ubuntu / Debian / RedHat Linux
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_EXEC="$(command -v python3 || command -v python || echo "python3")"

# Cron Markers
CRON_START_TAG="# >>> ServerWatch Managed Cron Jobs >>>"
CRON_END_TAG="# <<< ServerWatch Managed Cron Jobs <<<"

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

show_help() {
    echo -e "${CYAN}${BOLD}ServerWatch Cron Automation Utility${NC}"
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  --install      Install ServerWatch scheduled cron jobs to user crontab"
    echo "  --show         Display current crontab entries"
    echo "  --remove       Safely remove only ServerWatch jobs from crontab"
    echo "  --help         Display this help message"
    echo ""
    echo -e "${BOLD}Cron Syntax Primer:${NC}"
    echo "  ┌───────────── minute (0 - 59)"
    echo "  │ ┌───────────── hour (0 - 23)"
    echo "  │ │ ┌───────────── day of month (1 - 31)"
    echo "  │ │ │ ┌───────────── month (1 - 12)"
    echo "  │ │ │ │ ┌───────────── day of week (0 - 6) (Sunday to Saturday)"
    echo "  * * * * * command to execute"
}

show_crontab() {
    echo -e "${CYAN}${BOLD}--- Current User Crontab Entries ---${NC}"
    if crontab -l 2>/dev/null; then
        :
    else
        echo -e "${YELLOW}No crontab entries currently exist for user $(whoami).${NC}"
    fi
}

remove_crontab() {
    echo -e "${YELLOW}Removing ServerWatch managed jobs from crontab...${NC}"
    if ! crontab -l 2>/dev/null | grep -q "$CRON_START_TAG"; then
        echo -e "${GREEN}No ServerWatch cron jobs found. Nothing to remove.${NC}"
        return 0
    fi

    # Filter out blocks between markers
    crontab -l 2>/dev/null | sed "/$CRON_START_TAG/,/$CRON_END_TAG/d" | crontab -
    echo -e "${GREEN}Successfully removed ServerWatch jobs from crontab.${NC}"
}

install_crontab() {
    echo -e "${CYAN}${BOLD}Installing ServerWatch Automated Maintenance & Monitoring Jobs...${NC}"
    echo -e "Project Base Directory: ${PROJECT_ROOT}"
    echo -e "Python Interpreter:     ${PYTHON_EXEC}"

    # Remove existing jobs first to avoid duplicate blocks
    if crontab -l 2>/dev/null | grep -q "$CRON_START_TAG"; then
        echo -e "${YELLOW}Existing ServerWatch block detected. Updating configuration...${NC}"
        crontab -l 2>/dev/null | sed "/$CRON_START_TAG/,/$CRON_END_TAG/d" | crontab -
    fi

    # Generate new cron block
    NEW_JOBS=$(cat <<EOF
$CRON_START_TAG
# 1. System Telemetry & Threshold Check: Every 5 minutes
*/5 * * * * cd $PROJECT_ROOT && $PYTHON_EXEC -m automation.scheduler --once >> $PROJECT_ROOT/logs/scheduler_cron.log 2>&1

# 2. Disk Space Monitoring & Alerting: Every hour
0 * * * * cd $PROJECT_ROOT && bash scripts/disk_monitor.sh 85 >> $PROJECT_ROOT/logs/disk_cron.log 2>&1

# 3. Core Linux Services Health Audit: Every 30 minutes
*/30 * * * * cd $PROJECT_ROOT && bash scripts/service_monitor.sh >> $PROJECT_ROOT/logs/service_cron.log 2>&1

# 4. Daily Server Health & Incident Report Generation: Daily at 00:00 (Midnight)
0 0 * * * cd $PROJECT_ROOT && $PYTHON_EXEC -m automation.scheduler --report >> $PROJECT_ROOT/logs/report_cron.log 2>&1

# 5. Weekly Safe Log Archival & Backup: Every Sunday at 02:00 AM
0 2 * * 0 cd $PROJECT_ROOT && bash scripts/backup_logs.sh logs backups >> $PROJECT_ROOT/logs/backup_cron.log 2>&1

# 6. Weekly Prune of Old Transient Files (older than 14 days): Every Sunday at 03:00 AM (Dry-run by default)
0 3 * * 0 cd $PROJECT_ROOT && bash scripts/log_cleanup.sh --days 14 --dir logs --dry-run >> $PROJECT_ROOT/logs/cleanup_cron.log 2>&1
$CRON_END_TAG
EOF
)

    # Append to existing crontab
    CURRENT_CRON=$(crontab -l 2>/dev/null || true)
    if [ -n "$CURRENT_CRON" ]; then
        printf "%s\n\n%s\n" "$CURRENT_CRON" "$NEW_JOBS" | crontab -
    else
        printf "%s\n" "$NEW_JOBS" | crontab -
    fi

    echo -e "${GREEN}${BOLD}ServerWatch cron schedule installed successfully!${NC}"
    echo ""
    show_crontab
}

# Main Execution Routing
ACTION="${1:---help}"
case "$ACTION" in
    --install)
        install_crontab
        ;;
    --show|--status)
        show_crontab
        ;;
    --remove)
        remove_crontab
        ;;
    --help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}Unknown command: $ACTION${NC}"
        show_help
        exit 1
        ;;
esac

#!/usr/bin/env bash
# ==============================================================================
# ServerWatch - Linux Core Service Availability & State Monitor
# Script: service_monitor.sh
# Purpose: Inspect systemd services, identify degraded/failed units, and report status
# Target OS: Ubuntu / Debian / RedHat Linux
# ==============================================================================

set -euo pipefail

# Default monitored services
DEFAULT_SERVICES=("ssh" "cron" "systemd-journald" "rsyslog" "ufw" "nginx" "docker")
SERVICES=("${@:-${DEFAULT_SERVICES[@]}}")

REPORT_LOG="${SERVERWATCH_SERVICE_LOG:-logs/service_status.log}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${CYAN}${BOLD}================================================================${NC}"
echo -e "${CYAN}${BOLD}        ServerWatch - Linux Service Health & Audit              ${NC}"
echo -e "${CYAN}${BOLD}================================================================${NC}"

mkdir -p "$(dirname "$REPORT_LOG")"

ACTIVE_COUNT=0
INACTIVE_COUNT=0
FAILED_COUNT=0
NOT_FOUND_COUNT=0

printf "%-25s %-15s %-15s %-25s\n" "Service Name" "Active State" "Startup State" "Operational Status"
echo "--------------------------------------------------------------------------------------------------"

for svc in "${SERVICES[@]}"; do
    if command -v systemctl >/dev/null 2>&1; then
        # Check if unit file exists
        if ! systemctl list-unit-files "$svc.service" >/dev/null 2>&1 && ! systemctl status "$svc" >/dev/null 2>&1; then
            printf "%-25s %-15s %-15s %-25s\n" "$svc" "not-found" "uninstalled" "${YELLOW}[NOT INSTALLED]${NC}"
            NOT_FOUND_COUNT=$((NOT_FOUND_COUNT + 1))
            continue
        fi

        active_state=$(systemctl is-active "$svc" 2>/dev/null || echo "inactive")
        startup_state=$(systemctl is-enabled "$svc" 2>/dev/null || echo "disabled")

        if [ "$active_state" = "active" ]; then
            status_col="${GREEN}[RUNNING]${NC}"
            ACTIVE_COUNT=$((ACTIVE_COUNT + 1))
        elif [ "$active_state" = "failed" ]; then
            status_col="${RED}${BOLD}[FAILED]${NC}"
            FAILED_COUNT=$((FAILED_COUNT + 1))
        else
            status_col="${YELLOW}[INACTIVE]${NC}"
            INACTIVE_COUNT=$((INACTIVE_COUNT + 1))
        fi
        printf "%-25s %-15s %-15s " "$svc" "$active_state" "$startup_state"
        echo -e "$status_col"
    elif command -v service >/dev/null 2>&1; then
        # SysVinit fallback
        if service "$svc" status >/dev/null 2>&1; then
            printf "%-25s %-15s %-15s %-25s\n" "$svc" "running" "unknown" "${GREEN}[RUNNING]${NC}"
            ACTIVE_COUNT=$((ACTIVE_COUNT + 1))
        else
            printf "%-25s %-15s %-15s %-25s\n" "$svc" "stopped" "unknown" "${YELLOW}[STOPPED]${NC}"
            INACTIVE_COUNT=$((INACTIVE_COUNT + 1))
        fi
    else
        printf "%-25s %-15s %-15s %-25s\n" "$svc" "unknown" "unknown" "${YELLOW}[NO INIT FOUND]${NC}"
    fi
done

# Check systemd degraded units globally
echo -e "\n${BOLD}Globally Degraded or Failed Systemd Units:${NC}"
if command -v systemctl >/dev/null 2>&1; then
    FAILED_UNITS=$(systemctl --failed --no-legend 2>/dev/null || true)
    if [ -n "$FAILED_UNITS" ]; then
        echo -e "${RED}${BOLD}Warning: The following systemd units are currently in a FAILED state:${NC}"
        echo "$FAILED_UNITS" | sed 's/^/  /'
    else
        echo -e "${GREEN}No systemd units currently reported in failed state.${NC}"
    fi
fi

# Summary
echo -e "\n${BOLD}Summary:${NC} Active: ${GREEN}${ACTIVE_COUNT}${NC} | Inactive: ${YELLOW}${INACTIVE_COUNT}${NC} | Failed: ${RED}${FAILED_COUNT}${NC} | Not Installed: ${NOT_FOUND_COUNT}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] SERVICE_AUDIT | Active: ${ACTIVE_COUNT} | Inactive: ${INACTIVE_COUNT} | Failed: ${FAILED_COUNT}" >> "$REPORT_LOG"

if [ "$FAILED_COUNT" -gt 0 ]; then
    echo -e "${RED}${BOLD}One or more essential services have failed. Action recommended.${NC}"
    exit 2
else
    echo -e "${GREEN}Service scan completed without critical failures.${NC}"
    exit 0
fi

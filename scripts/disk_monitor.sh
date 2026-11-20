#!/usr/bin/env bash
# ==============================================================================
# ServerWatch - Linux Disk Space Monitoring & Alerting Utility
# Script: disk_monitor.sh
# Purpose: Inspect all mounted partitions and flag any partition exceeding threshold
# Target OS: Ubuntu / Debian / RedHat Linux
# ==============================================================================

set -euo pipefail

# Configurable threshold (default 85%)
THRESHOLD=${1:-85}
LOG_FILE="${SERVERWATCH_ALERT_LOG:-logs/alerts.log}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${CYAN}${BOLD}================================================================${NC}"
echo -e "${CYAN}${BOLD}     ServerWatch - Disk Space Monitoring (Threshold: ${THRESHOLD}%)     ${NC}"
echo -e "${CYAN}${BOLD}================================================================${NC}"

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

ALERTS_TRIGGERED=0

echo -e "\n${BOLD}Filesystem Breakdown:${NC}"
printf "%-25s %-10s %-10s %-10s %-8s %-20s %-10s\n" "Filesystem" "Size" "Used" "Avail" "Use%" "Mounted on" "Status"
echo "--------------------------------------------------------------------------------------------------"

# POSIX df with standard portable output (-P)
df -hP | tail -n +2 | while read -r fs size used avail usepct mountpoint; do
    # Filter virtual filesystems
    case "$fs" in
        tmpfs|devtmpfs|udev|overlay|none|/dev/loop*)
            continue
            ;;
    esac

    # Extract clean integer percentage
    usage_num="${usepct%\%}"

    if [ "$usage_num" -ge "$THRESHOLD" ]; then
        status="${RED}${BOLD}[CRITICAL]${NC}"
        echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] [CRITICAL] Resource: Disk ($mountpoint) | Observed: ${usage_num}% | Threshold: ${THRESHOLD}% | Message: Partition $mountpoint usage exceeded critical threshold" >> "$LOG_FILE"
        ALERTS_TRIGGERED=$((ALERTS_TRIGGERED + 1))
    elif [ "$usage_num" -ge $((THRESHOLD - 10)) ]; then
        status="${YELLOW}[WARNING]${NC}"
    else
        status="${GREEN}[OK]${NC}"
    fi

    printf "%-25s %-10s %-10s %-10s %-8s %-20s " "$fs" "$size" "$used" "$avail" "$usepct" "$mountpoint"
    echo -e "$status"
done

# Disk Inode Consumption (important for Linux servers when many small files fill inode table)
echo -e "\n${BOLD}Inode Usage Breakdown:${NC}"
printf "%-25s %-10s %-10s %-10s %-8s %-20s\n" "Filesystem" "Inodes" "IUsed" "IFree" "IUse%" "Mounted on"
echo "--------------------------------------------------------------------------------------------------"
df -iP | tail -n +2 | while read -r fs inodes iused ifree iusepct mountpoint; do
    case "$fs" in
        tmpfs|devtmpfs|udev|overlay|none|/dev/loop*)
            continue
            ;;
    esac
    printf "%-25s %-10s %-10s %-10s %-8s %-20s\n" "$fs" "$inodes" "$iused" "$ifree" "$iusepct" "$mountpoint"
done

echo -e "\n${CYAN}Disk monitoring completed.${NC}"
if [ "$ALERTS_TRIGGERED" -gt 0 ]; then
    echo -e "${RED}${BOLD}Alert: One or more disk partitions exceeded the ${THRESHOLD}% threshold!${NC}"
    exit 1
else
    echo -e "${GREEN}All monitored partitions are within safe operational limits.${NC}"
    exit 0
fi

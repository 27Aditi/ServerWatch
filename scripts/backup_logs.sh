#!/usr/bin/env bash
# ==============================================================================
# ServerWatch - Log Archival & Backup Utility
# Script: backup_logs.sh
# Purpose: Create timestamped compressed gzip tarball of application logs
# Target OS: Ubuntu / Debian / RedHat Linux
# ==============================================================================

set -euo pipefail

SOURCE_DIR="${1:-logs}"
BACKUP_DIR="${2:-backups}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
ARCHIVE_NAME="serverwatch_logs_${TIMESTAMP}.tar.gz"
DESTINATION="${BACKUP_DIR}/${ARCHIVE_NAME}"
MAINTENANCE_LOG="logs/maintenance.log"

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${CYAN}${BOLD}================================================================${NC}"
echo -e "${CYAN}${BOLD}            ServerWatch - Log Archival & Backup                 ${NC}"
echo -e "${CYAN}${BOLD}================================================================${NC}"

# Check source directory
if [ ! -d "$SOURCE_DIR" ]; then
    echo -e "${RED}Error: Source directory '$SOURCE_DIR' does not exist.${NC}"
    exit 1
fi

# Ensure backup destination directory exists
mkdir -p "$BACKUP_DIR"
mkdir -p "$(dirname "$MAINTENANCE_LOG")"

# Check available disk space in backup partition (require at least 50MB free)
if command -v df >/dev/null 2>&1; then
    AVAIL_KB=$(df -k "$BACKUP_DIR" | tail -1 | awk '{print $4}')
    if [ "$AVAIL_KB" -lt 51200 ]; then
        echo -e "${RED}Error: Insufficient disk space in backup destination. (< 50MB free)${NC}"
        exit 1
    fi
fi

echo -e "Archiving logs from:   ${BOLD}${SOURCE_DIR}${NC}"
echo -e "Creating archive:      ${BOLD}${DESTINATION}${NC}"

# Create gzip compressed tarball safely
# Excluding any nested backups or transient locks
tar -czf "$DESTINATION" \
    --exclude="*.tmp" \
    --exclude="*.lock" \
    "$SOURCE_DIR" 2>/dev/null || {
        echo -e "${RED}Tar command encountered an error while compressing files.${NC}"
        exit 1
    }

ARCHIVE_SIZE=$(du -h "$DESTINATION" | cut -f1)

echo -e "${GREEN}${BOLD}Backup created successfully!${NC}"
echo -e "  Archive File: ${DESTINATION}"
echo -e "  Archive Size: ${ARCHIVE_SIZE}"

# Record in maintenance audit log
echo "[$(date '+%Y-%m-%d %H:%M:%S')] LOG_BACKUP_CREATED | Source: ${SOURCE_DIR} | Archive: ${DESTINATION} | Size: ${ARCHIVE_SIZE}" >> "$MAINTENANCE_LOG"

echo -e "${CYAN}${BOLD}================================================================${NC}"

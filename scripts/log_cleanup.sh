#!/usr/bin/env bash
# ==============================================================================
# ServerWatch - Safe Log & Temp File Cleanup Utility
# Script: log_cleanup.sh
# Purpose: Identify and safely prune old log / temporary files with strict
#          confirmation safeguards and audit logging.
# Target OS: Ubuntu / Debian / RedHat Linux
# ==============================================================================

set -euo pipefail

# Default settings
RETENTION_DAYS=7
TARGET_DIR="${SERVERWATCH_LOG_DIR:-logs}"
CONFIRM_DELETE=false
DRY_RUN=true
CLEANUP_LOG="${SERVERWATCH_CLEANUP_LOG:-logs/maintenance.log}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Parse flags
while [[ $# -gt 0 ]]; do
    case "$1" in
        --days|-d)
            RETENTION_DAYS="$2"
            shift 2
            ;;
        --dir)
            TARGET_DIR="$2"
            shift 2
            ;;
        --confirm)
            CONFIRM_DELETE=true
            DRY_RUN=false
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            CONFIRM_DELETE=false
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--days <retention_days>] [--dir <directory>] [--confirm] [--dry-run]"
            echo "Options:"
            echo "  --days, -d     Number of retention days (files older than this are selected). Default: 7"
            echo "  --dir          Target directory to clean (Default: logs)"
            echo "  --confirm      Execute actual deletion with explicit confirmation"
            echo "  --dry-run      Scan and report files only (Default: active)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo -e "${CYAN}${BOLD}================================================================${NC}"
echo -e "${CYAN}${BOLD}       ServerWatch - Safe Log & Temporary File Cleanup          ${NC}"
echo -e "${CYAN}${BOLD}================================================================${NC}"
echo -e "Target Directory: ${TARGET_DIR}"
echo -e "Retention Policy: Older than ${RETENTION_DAYS} days"
echo -e "Execution Mode:   $([ "$DRY_RUN" = true ] && echo -e "${YELLOW}DRY-RUN (Safe Simulation)${NC}" || echo -e "${RED}${BOLD}LIVE DELETION CONFIRMED${NC}")"

mkdir -p "$(dirname "$CLEANUP_LOG")"

if [ ! -d "$TARGET_DIR" ]; then
    echo -e "${YELLOW}Target directory '$TARGET_DIR' does not exist. Nothing to clean.${NC}"
    exit 0
fi

# Find candidate files (logs older than retention days, excluding essential active files)
# Safe search matching .log, .jsonl, .tmp, .gz
OLD_FILES=$(find "$TARGET_DIR" -type f \( -name "*.log.*" -o -name "*.gz" -o -name "*.tmp" -o -name "*.old" \) -mtime +"$RETENTION_DAYS" 2>/dev/null || true)

# Count and compute size
FILE_COUNT=0
TOTAL_SIZE=0

if [ -n "$OLD_FILES" ]; then
    FILE_COUNT=$(echo "$OLD_FILES" | grep -c . || true)
fi

echo -e "\n${BOLD}Files Eligible for Cleanup:${NC}"
if [ "$FILE_COUNT" -eq 0 ]; then
    echo -e "${GREEN}No files older than ${RETENTION_DAYS} days found in ${TARGET_DIR}.${NC}"
    exit 0
fi

echo "$OLD_FILES" | while read -r file; do
    if [ -f "$file" ]; then
        sz=$(du -h "$file" | cut -f1)
        mtime=$(date -r "$file" "+%Y-%m-%d %H:%M:%S" 2>/dev/null || stat -c %y "$file" 2>/dev/null || echo "N/A")
        echo -e "  - ${file} (${sz}, last modified: ${mtime})"
    fi
done

echo -e "\nTotal candidates identified: ${BOLD}${FILE_COUNT}${NC}"

if [ "$DRY_RUN" = true ]; then
    echo -e "\n${YELLOW}${BOLD}[NOTICE] Operating in DRY-RUN mode.${NC}"
    echo -e "No files were modified or deleted. To execute actual deletion, run:"
    echo -e "  ${BOLD}$0 --days ${RETENTION_DAYS} --dir ${TARGET_DIR} --confirm${NC}"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] DRY_RUN_CLEANUP | Dir: ${TARGET_DIR} | Eligible Files: ${FILE_COUNT} | Retention: ${RETENTION_DAYS}d" >> "$CLEANUP_LOG"
    exit 0
fi

# Live deletion requires confirmed flag
if [ "$CONFIRM_DELETE" = true ]; then
    echo -e "\n${RED}${BOLD}Proceeding with confirmed deletion...${NC}"
    DELETED_COUNT=0
    echo "$OLD_FILES" | while read -r file; do
        if [ -f "$file" ]; then
            rm -f "$file"
            echo -e "  ${GREEN}Deleted:${NC} $file"
            DELETED_COUNT=$((DELETED_COUNT + 1))
        fi
    done
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] CONFIRMED_CLEANUP | Dir: ${TARGET_DIR} | Deleted Files: ${FILE_COUNT} | Retention: ${RETENTION_DAYS}d" >> "$CLEANUP_LOG"
    echo -e "\n${GREEN}${BOLD}Cleanup completed successfully. Audit log updated: ${CLEANUP_LOG}${NC}"
fi

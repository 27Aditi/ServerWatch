#!/usr/bin/env bash
# ==============================================================================
# ServerWatch - Linux System Information Utility
# Script: system_info.sh
# Purpose: Display detailed operating system, kernel, CPU, memory, and uptime
# Target OS: Ubuntu / Debian / RedHat Linux
# ==============================================================================

set -euo pipefail

# ANSI Color Codes for terminal readability
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BLUE}${BOLD}================================================================${NC}"
echo -e "${CYAN}${BOLD}       ServerWatch - Host Infrastructure System Info           ${NC}"
echo -e "${BLUE}${BOLD}================================================================${NC}"

# 1. Operating System Details
echo -e "\n${YELLOW}${BOLD}[1] Operating System Information:${NC}"
if [ -f /etc/os-release ]; then
    # Standard modern Linux distribution release file
    # shellcheck source=/dev/null
    . /etc/os-release
    echo -e "  ${BOLD}Distribution:${NC}   ${NAME:-Linux} ${VERSION:-}"
    echo -e "  ${BOLD}Version ID:${NC}     ${VERSION_ID:-N/A}"
    echo -e "  ${BOLD}Codename:${NC}       ${VERSION_CODENAME:-N/A}"
else
    echo -e "  ${BOLD}OS Family:${NC}      $(uname -s)"
fi
echo -e "  ${BOLD}Hostname:${NC}       $(hostname -f 2>/dev/null || hostname)"
echo -e "  ${BOLD}Architecture:${NC}   $(uname -m)"

# 2. Kernel Information
echo -e "\n${YELLOW}${BOLD}[2] Linux Kernel Version:${NC}"
echo -e "  ${BOLD}Kernel Release:${NC} $(uname -r)"
echo -e "  ${BOLD}Kernel Build:${NC}   $(uname -v)"

# 3. System Uptime & Boot Time
echo -e "\n${YELLOW}${BOLD}[3] System Uptime & Availability:${NC}"
if command -v uptime >/dev/null 2>&1; then
    echo -e "  ${BOLD}Uptime Summary:${NC} $(uptime)"
fi
if command -v who >/dev/null 2>&1; then
    echo -e "  ${BOLD}Last Boot:${NC}      $(who -b 2>/dev/null | awk '{print $3, $4}' || echo 'N/A')"
fi

# 4. CPU Hardware Telemetry
echo -e "\n${YELLOW}${BOLD}[4] CPU Specifications:${NC}"
if [ -f /proc/cpuinfo ]; then
    CPU_MODEL=$(grep -m1 "model name" /proc/cpuinfo | cut -d: -f2 | sed 's/^[ \t]*//')
    CPU_CORES=$(grep -c "^processor" /proc/cpuinfo)
    echo -e "  ${BOLD}Model Name:${NC}     ${CPU_MODEL:-Standard Processor}"
    echo -e "  ${BOLD}Logical Cores:${NC}  ${CPU_CORES}"
elif command -v lscpu >/dev/null 2>&1; then
    lscpu | grep -E "Model name|CPU\(s\):|Thread\(s\) per core" | sed 's/^/  /'
else
    echo -e "  ${BOLD}Logical Cores:${NC}  $(nproc 2>/dev/null || echo 1)"
fi

# 5. Memory & Swap Utilization
echo -e "\n${YELLOW}${BOLD}[5] Memory & Swap Usage:${NC}"
if command -v free >/dev/null 2>&1; then
    free -h
elif [ -f /proc/meminfo ]; then
    grep -E "MemTotal|MemFree|MemAvailable|SwapTotal|SwapFree" /proc/meminfo | sed 's/^/  /'
fi

# 6. Current System Load Average
echo -e "\n${YELLOW}${BOLD}[6] System Load Average (1m, 5m, 15m):${NC}"
if [ -f /proc/loadavg ]; then
    echo -e "  ${BOLD}Load Average:${NC}   $(cat /proc/loadavg)"
fi

echo -e "\n${GREEN}${BOLD}System information scan completed successfully.${NC}"
echo -e "${BLUE}${BOLD}================================================================${NC}"

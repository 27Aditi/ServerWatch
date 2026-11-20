#!/usr/bin/env bash
# ==============================================================================
# ServerWatch - Linux Process Consumption & Telemetry Monitor
# Script: process_monitor.sh
# Purpose: Identify top CPU and RAM consuming processes using ps and /proc
# Target OS: Ubuntu / Debian / RedHat Linux
# ==============================================================================

set -euo pipefail

LIMIT=${1:-10}

# Colors
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${CYAN}${BOLD}================================================================${NC}"
echo -e "${CYAN}${BOLD}      ServerWatch - Process Resource Monitor (Top ${LIMIT})      ${NC}"
echo -e "${CYAN}${BOLD}================================================================${NC}"

# 1. Total Process State Statistics
echo -e "\n${YELLOW}${BOLD}[1] Process State Distribution:${NC}"
TOTAL_PROCS=$(ps -ef | wc -l)
RUNNING_PROCS=$(ps -eo state | grep -c "R" || true)
SLEEPING_PROCS=$(ps -eo state | grep -c "S" || true)
ZOMBIE_PROCS=$(ps -eo state | grep -c "Z" || true)

echo -e "  Total Processes:    ${TOTAL_PROCS}"
echo -e "  Running (R):        ${RUNNING_PROCS}"
echo -e "  Sleeping (S):       ${SLEEPING_PROCS}"
if [ "$ZOMBIE_PROCS" -gt 0 ]; then
    echo -e "  Zombie (Z):         ${BOLD}\033[0;31m${ZOMBIE_PROCS} (Warning: Defunct processes detected)${NC}"
else
    echo -e "  Zombie (Z):         0"
fi

# 2. Top CPU-Consuming Processes
echo -e "\n${YELLOW}${BOLD}[2] Top ${LIMIT} Processes by CPU Consumption:${NC}"
echo -e "  ${BOLD}Explanation:${NC} High CPU consumers may indicate compute workloads, infinite loops, or runaway threads."
echo "--------------------------------------------------------------------------------------------------"
printf "%-8s %-12s %-8s %-8s %-10s %-12s %-25s\n" "PID" "USER" "%CPU" "%MEM" "TIME" "STAT" "COMMAND"
echo "--------------------------------------------------------------------------------------------------"
ps -eo pid,user,%cpu,%mem,time,stat,comm --sort=-%cpu | head -n "$((LIMIT + 1))" | tail -n "$LIMIT" | while read -r pid user cpu mem ptime stat comm; do
    printf "%-8s %-12s %-8s %-8s %-10s %-12s %-25s\n" "$pid" "$user" "$cpu" "$mem" "$ptime" "$stat" "$comm"
done

# 3. Top Memory-Consuming Processes
echo -e "\n${YELLOW}${BOLD}[3] Top ${LIMIT} Processes by Memory (RSS) Consumption:${NC}"
echo -e "  ${BOLD}Explanation:${NC} Memory-heavy processes risk invoking the Linux OOM (Out-Of-Memory) killer."
echo "--------------------------------------------------------------------------------------------------"
printf "%-8s %-12s %-8s %-8s %-10s %-12s %-25s\n" "PID" "USER" "%MEM" "%CPU" "RSS(KB)" "STAT" "COMMAND"
echo "--------------------------------------------------------------------------------------------------"
ps -eo pid,user,%mem,%cpu,rss,stat,comm --sort=-%mem | head -n "$((LIMIT + 1))" | tail -n "$LIMIT" | while read -r pid user mem cpu rss stat comm; do
    printf "%-8s %-12s %-8s %-8s %-10s %-12s %-25s\n" "$pid" "$user" "$mem" "$cpu" "$rss" "$stat" "$comm"
done

echo -e "\n${GREEN}${BOLD}Process monitoring snapshot completed.${NC}"
echo -e "${CYAN}${BOLD}================================================================${NC}"

"""
ServerWatch - Report Generator Module
Synthesizes system telemetry and incident logs into actionable executive
and operational health reports (Markdown, JSON, CSV).
"""

import os
import csv
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from .incident_manager import IncidentManager
from monitoring.metrics import SystemMetricsCollector

logger = logging.getLogger("serverwatch.reports")


class ReportGenerator:
    """Generates comprehensive system health and incident reports."""

    def __init__(self, reports_dir: str = "reports"):
        self.reports_dir = reports_dir
        self.incident_manager = IncidentManager()
        self.metrics_collector = SystemMetricsCollector()
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        if not os.path.exists(self.reports_dir):
            os.makedirs(self.reports_dir, exist_ok=True)

    def generate_health_report(self) -> Dict[str, str]:
        """
        Generate a Markdown and JSON daily health report combining current
        metrics and incident statistics.
        """
        now = datetime.now()
        timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")
        file_suffix = now.strftime("%Y%m%d_%H%M%S")

        snapshot = self.metrics_collector.collect_snapshot()
        sys_info = snapshot.get("system", {})
        cpu = snapshot.get("cpu", {})
        mem = snapshot.get("memory", {})
        disk = snapshot.get("disk", {})
        net = snapshot.get("network", {})
        stats = self.incident_manager.get_statistics()
        active_incidents = self.incident_manager.get_incidents(status="ACTIVE")

        # Determine overall server health score
        health_status = "HEALTHY"
        if stats["critical"] > 0 or cpu.get("utilization_percent", 0) > 85 or mem.get("utilization_percent", 0) > 90:
            health_status = "CRITICAL"
        elif stats["high"] > 0 or cpu.get("utilization_percent", 0) > 70 or mem.get("utilization_percent", 0) > 75:
            health_status = "WARNING"

        # Build Markdown content
        md_lines = [
            f"# ServerWatch Health & Infrastructure Report",
            f"**Generated:** {timestamp_str}  ",
            f"**Server Hostname:** `{sys_info.get('hostname')}`  ",
            f"**Overall Health Status:** `{health_status}`  ",
            "",
            "---",
            "",
            "## 1. Executive System Summary",
            f"- **Operating System:** {sys_info.get('distro')} ({sys_info.get('architecture')})",
            f"- **Kernel Version:** {sys_info.get('kernel_release')}",
            f"- **System Uptime:** {sys_info.get('uptime_human')}",
            f"- **Boot Timestamp:** {sys_info.get('boot_time')}",
            f"- **Logical Cores:** {cpu.get('logical_cores')} | **Physical:** {cpu.get('physical_cores')}",
            "",
            "## 2. Resource Utilization Snapshot",
            f"| Resource | Current Utilization | Available / Total | Status |",
            f"| :--- | :--- | :--- | :--- |",
            f"| **CPU Usage** | `{cpu.get('utilization_percent')}%` | Load: {cpu.get('load_1m')}, {cpu.get('load_5m')}, {cpu.get('load_15m')} | {'CRITICAL' if cpu.get('utilization_percent', 0) > 80 else 'OK'} |",
            f"| **Memory (RAM)** | `{mem.get('utilization_percent')}%` | {mem.get('available_human')} free / {mem.get('total_human')} | {'CRITICAL' if mem.get('utilization_percent', 0) > 85 else 'OK'} |",
            f"| **Swap Space** | `{mem.get('swap_percent')}%` | {mem.get('swap_used_human')} used / {mem.get('swap_total_human')} | {'WARN' if mem.get('swap_percent', 0) > 50 else 'OK'} |",
            f"| **Primary Disk** | `{disk.get('max_utilization_percent')}%` | Partitions evaluated: {len(disk.get('partitions', []))} | {'CRITICAL' if disk.get('max_utilization_percent', 0) > 85 else 'OK'} |",
            f"| **Network Transfer** | Tx: {net.get('bytes_sent_human')} | Rx: {net.get('bytes_recv_human')} | Active |",
            "",
            "### Disk Partitions Breakdown",
        ]

        for p in disk.get("partitions", []):
            md_lines.append(
                f"- Mount `{p['mountpoint']}` ({p['device']}) - "
                f"**{p['utilization_percent']}% used** ({p['used_human']} of {p['total_human']})"
            )

        md_lines.extend([
            "",
            "## 3. Incident Management Overview",
            f"- **Total Incidents Recorded:** {stats['total']}",
            f"- **Active Incidents Requiring Attention:** {stats['active']}",
            f"- **Currently Under Investigation:** {stats['investigating']}",
            f"- **Resolved Incidents:** {stats['resolved']}",
            f"- **Critical Severity Count:** {stats['critical']}",
            f"- **High Severity Count:** {stats['high']}",
            "",
            "### Active Incidents List",
        ])

        if active_incidents:
            for inc in active_incidents:
                md_lines.append(
                    f"- **[{inc['severity']}] {inc['incident_id']}** ({inc['category']}): "
                    f"{inc['description']} (Resource: `{inc['affected_resource']}` | Reported: {inc['timestamp']})"
                )
        else:
            md_lines.append("_No active incidents currently reported. Infrastructure operating normally._")

        md_lines.extend([
            "",
            "## 4. Maintenance Recommendations",
            "1. Run `log_cleanup.sh` if `/var/log` or application logs exceed configured retention.",
            "2. Execute `backup_logs.sh` prior to performing kernel or OS package updates.",
            "3. Verify failed systemd services using `service_monitor.sh`.",
            "",
            "---",
            "*Report compiled automatically by ServerWatch Infrastructure Engineering Suite.*"
        ])

        md_content = "\n".join(md_lines)
        md_filename = os.path.join(self.reports_dir, f"health_report_{file_suffix}.md")
        json_filename = os.path.join(self.reports_dir, f"health_report_{file_suffix}.json")

        with open(md_filename, "w", encoding="utf-8") as f:
            f.write(md_content)

        report_data = {
            "metadata": {
                "report_id": f"REP-{file_suffix}",
                "generated_at": timestamp_str,
                "health_status": health_status
            },
            "snapshot": snapshot,
            "incident_statistics": stats,
            "active_incidents": active_incidents
        }

        with open(json_filename, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)

        logger.info(f"Generated health reports: {md_filename} and {json_filename}")
        return {
            "markdown_path": md_filename,
            "json_path": json_filename,
            "content": md_content
        }

    def export_incidents_csv(self, filename: Optional[str] = None) -> str:
        """Export all recorded incidents to CSV format."""
        if not filename:
            file_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(self.reports_dir, f"incidents_export_{file_suffix}.csv")

        incidents = self.incident_manager.get_incidents()
        fieldnames = [
            "incident_id", "timestamp", "last_seen", "category", "severity",
            "affected_resource", "description", "status", "occurrence_count",
            "resolution", "resolved_at"
        ]

        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            for inc in incidents:
                writer.writerow(inc)

        logger.info(f"Exported {len(incidents)} incidents to {filename}")
        return filename

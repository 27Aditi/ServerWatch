"""
ServerWatch - Automated Scheduler & Background Runner
Runs periodic system monitoring cycles, checks alert thresholds,
records time-series metrics, logs incidents, and generates daily reports.
Can be executed as a one-shot task (from Cron) or as a continuous daemon.
"""

import os
import sys
import time
import argparse
import logging
from datetime import datetime
from typing import Dict, Any

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from monitoring.metrics import SystemMetricsCollector, load_config
from monitoring.alerts import AlertEngine, AlertSeverity
from incident_management.incident_manager import IncidentManager, IncidentCategory
from incident_management.report_generator import ReportGenerator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("serverwatch.scheduler")


class ServerWatchScheduler:
    """Orchestrates periodic monitoring checks, alert evaluations, and reports."""

    def __init__(self, config_path: str = "config/settings.json"):
        self.config = load_config(config_path)
        self.metrics_collector = SystemMetricsCollector(config_path)
        self.alert_engine = AlertEngine(config_path)
        self.incident_manager = IncidentManager()
        self.report_generator = ReportGenerator()
        self.interval = self.config.get("system", {}).get("collection_interval_seconds", 15)

    def run_single_cycle(self) -> Dict[str, Any]:
        """Execute one complete monitoring, alerting, and incident-eval cycle."""
        logger.info("Executing monitoring telemetry cycle...")
        snapshot = self.metrics_collector.record_snapshot()

        # Evaluate thresholds
        alerts = self.alert_engine.evaluate(snapshot)

        # Automatically translate CRITICAL or HIGH alerts into managed Incidents
        for alert in alerts:
            severity = alert.get("severity")
            if severity in [AlertSeverity.CRITICAL, AlertSeverity.HIGH]:
                category = IncidentCategory.RESOURCE_EXHAUSTION
                if "Disk" in alert.get("resource", ""):
                    category = IncidentCategory.DISK_PRESSURE
                elif "Load" in alert.get("resource", ""):
                    category = IncidentCategory.HIGH_LOAD

                self.incident_manager.create_incident(
                    category=category,
                    severity=severity,
                    description=alert.get("message", "Threshold exceeded"),
                    affected_resource=alert.get("resource", "System"),
                    notes=f"Auto-generated from alert {alert.get('alert_id')}"
                )

        logger.info(
            f"Cycle completed. CPU: {snapshot['cpu']['utilization_percent']}% | "
            f"RAM: {snapshot['memory']['utilization_percent']}% | "
            f"Partitions: {len(snapshot['disk']['partitions'])} | "
            f"Alerts Triggered: {len(alerts)}"
        )
        return {
            "snapshot": snapshot,
            "alerts": alerts
        }

    def run_daemon(self, max_cycles: int = 0) -> None:
        """Run continuous background monitoring loop."""
        logger.info(f"Starting ServerWatch Monitoring Daemon (Polling interval: {self.interval}s)...")
        cycles = 0
        try:
            while True:
                self.run_single_cycle()
                cycles += 1
                if max_cycles > 0 and cycles >= max_cycles:
                    logger.info(f"Reached specified limit of {max_cycles} cycles. Terminating.")
                    break
                time.sleep(self.interval)
        except KeyboardInterrupt:
            logger.info("ServerWatch Daemon received interrupt signal. Exiting gracefully.")

    def generate_report(self) -> str:
        """Generate on-demand executive health report."""
        result = self.report_generator.generate_health_report()
        logger.info(f"Health report generated: {result['markdown_path']}")
        return result['markdown_path']


def main():
    parser = argparse.ArgumentParser(description="ServerWatch Automated Monitoring and Scheduler")
    parser.add_argument("--once", action="store_true", help="Run a single monitoring cycle and exit (ideal for cron)")
    parser.add_argument("--daemon", action="store_true", help="Run as a continuous monitoring loop")
    parser.add_argument("--report", action="store_true", help="Generate an immediate health report and exit")
    parser.add_argument("--interval", type=int, default=0, help="Override polling interval in seconds")
    parser.add_argument("--cycles", type=int, default=0, help="Max cycles to run in daemon mode (0 = infinite)")

    args = parser.parse_args()
    scheduler = ServerWatchScheduler()

    if args.interval > 0:
        scheduler.interval = args.interval

    if args.report:
        report_path = scheduler.generate_report()
        print(f"Report created at: {report_path}")
    elif args.once:
        scheduler.run_single_cycle()
    elif args.daemon:
        scheduler.run_daemon(max_cycles=args.cycles)
    else:
        # Default behavior: run once if not specified
        scheduler.run_single_cycle()


if __name__ == "__main__":
    main()

"""
ServerWatch - Threshold-based Alerting Module
Evaluates real-time system metrics against configurable thresholds,
determines severity levels, and persists structured alert records.
"""

import os
import json
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger("serverwatch.alerts")


class AlertSeverity:
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertStatus:
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class AlertEngine:
    """Evaluates metrics against thresholds, generates alerts, and manages alert history."""

    def __init__(self, config_path: str = "config/settings.json"):
        self.config_path = config_path
        self._load_config()
        self._ensure_paths()

    def _load_config(self) -> None:
        default_thresholds = {
            "cpu_warning_percent": 70.0,
            "cpu_critical_percent": 80.0,
            "memory_warning_percent": 75.0,
            "memory_critical_percent": 85.0,
            "disk_warning_percent": 75.0,
            "disk_critical_percent": 85.0,
            "load_warning_ratio": 1.5,
            "load_critical_ratio": 2.5
        }
        self.thresholds = default_thresholds
        self.alerts_log_path = "logs/alerts.log"
        self.alerts_data_path = "logs/alerts.json"

        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "thresholds" in data:
                        self.thresholds.update(data["thresholds"])
                    paths = data.get("paths", {})
                    self.alerts_log_path = paths.get("alerts_log", self.alerts_log_path)
            except Exception as e:
                logger.warning(f"Could not load {self.config_path}: {e}")

    def _ensure_paths(self) -> None:
        for path in [self.alerts_log_path, self.alerts_data_path]:
            directory = os.path.dirname(path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
        if not os.path.exists(self.alerts_data_path):
            with open(self.alerts_data_path, "w", encoding="utf-8") as f:
                json.dump([], f)

    def evaluate(self, snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Evaluate a metrics snapshot against thresholds.
        Returns a list of generated alert objects.
        """
        generated_alerts: List[Dict[str, Any]] = []
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. CPU Evaluation
        cpu_data = snapshot.get("cpu", {})
        cpu_pct = cpu_data.get("utilization_percent", 0.0)
        cpu_crit = self.thresholds.get("cpu_critical_percent", 80.0)
        cpu_warn = self.thresholds.get("cpu_warning_percent", 70.0)

        if cpu_pct >= cpu_crit:
            generated_alerts.append({
                "alert_id": f"ALT-{uuid.uuid4().hex[:8].upper()}",
                "timestamp": now_str,
                "resource": "CPU",
                "metric_name": "utilization_percent",
                "observed_value": cpu_pct,
                "threshold_value": cpu_crit,
                "severity": AlertSeverity.CRITICAL,
                "message": f"CPU utilization reached {cpu_pct:.1f}% (critical threshold: {cpu_crit:.1f}%)",
                "status": AlertStatus.ACTIVE
            })
        elif cpu_pct >= cpu_warn:
            generated_alerts.append({
                "alert_id": f"ALT-{uuid.uuid4().hex[:8].upper()}",
                "timestamp": now_str,
                "resource": "CPU",
                "metric_name": "utilization_percent",
                "observed_value": cpu_pct,
                "threshold_value": cpu_warn,
                "severity": AlertSeverity.HIGH,
                "message": f"CPU utilization reached {cpu_pct:.1f}% (warning threshold: {cpu_warn:.1f}%)",
                "status": AlertStatus.ACTIVE
            })

        # 2. System Load Average Evaluation
        load_ratio = cpu_data.get("load_ratio_1m", 0.0)
        load_crit = self.thresholds.get("load_critical_ratio", 2.5)
        load_warn = self.thresholds.get("load_warning_ratio", 1.5)

        if load_ratio >= load_crit:
            generated_alerts.append({
                "alert_id": f"ALT-{uuid.uuid4().hex[:8].upper()}",
                "timestamp": now_str,
                "resource": "System Load",
                "metric_name": "load_ratio_1m",
                "observed_value": load_ratio,
                "threshold_value": load_crit,
                "severity": AlertSeverity.CRITICAL,
                "message": f"1-minute load ratio reached {load_ratio:.2f} per core (critical: {load_crit:.2f})",
                "status": AlertStatus.ACTIVE
            })
        elif load_ratio >= load_warn:
            generated_alerts.append({
                "alert_id": f"ALT-{uuid.uuid4().hex[:8].upper()}",
                "timestamp": now_str,
                "resource": "System Load",
                "metric_name": "load_ratio_1m",
                "observed_value": load_ratio,
                "threshold_value": load_warn,
                "severity": AlertSeverity.MEDIUM,
                "message": f"1-minute load ratio reached {load_ratio:.2f} per core (warning: {load_warn:.2f})",
                "status": AlertStatus.ACTIVE
            })

        # 3. Memory Evaluation
        mem_data = snapshot.get("memory", {})
        mem_pct = mem_data.get("utilization_percent", 0.0)
        mem_crit = self.thresholds.get("memory_critical_percent", 85.0)
        mem_warn = self.thresholds.get("memory_warning_percent", 75.0)

        if mem_pct >= mem_crit:
            generated_alerts.append({
                "alert_id": f"ALT-{uuid.uuid4().hex[:8].upper()}",
                "timestamp": now_str,
                "resource": "RAM",
                "metric_name": "utilization_percent",
                "observed_value": mem_pct,
                "threshold_value": mem_crit,
                "severity": AlertSeverity.CRITICAL,
                "message": f"Memory utilization reached {mem_pct:.1f}% (critical threshold: {mem_crit:.1f}%)",
                "status": AlertStatus.ACTIVE
            })
        elif mem_pct >= mem_warn:
            generated_alerts.append({
                "alert_id": f"ALT-{uuid.uuid4().hex[:8].upper()}",
                "timestamp": now_str,
                "resource": "RAM",
                "metric_name": "utilization_percent",
                "observed_value": mem_pct,
                "threshold_value": mem_warn,
                "severity": AlertSeverity.HIGH,
                "message": f"Memory utilization reached {mem_pct:.1f}% (warning threshold: {mem_warn:.1f}%)",
                "status": AlertStatus.ACTIVE
            })

        # 4. Disk Partitions Evaluation
        disk_data = snapshot.get("disk", {})
        disk_crit = self.thresholds.get("disk_critical_percent", 85.0)
        disk_warn = self.thresholds.get("disk_warning_percent", 75.0)

        for partition in disk_data.get("partitions", []):
            dpct = partition.get("utilization_percent", 0.0)
            mount = partition.get("mountpoint", "/")
            if dpct >= disk_crit:
                generated_alerts.append({
                    "alert_id": f"ALT-{uuid.uuid4().hex[:8].upper()}",
                    "timestamp": now_str,
                    "resource": f"Disk ({mount})",
                    "metric_name": "utilization_percent",
                    "observed_value": dpct,
                    "threshold_value": disk_crit,
                    "severity": AlertSeverity.CRITICAL,
                    "message": f"Disk partition {mount} usage reached {dpct:.1f}% (critical: {disk_crit:.1f}%)",
                    "status": AlertStatus.ACTIVE
                })
            elif dpct >= disk_warn:
                generated_alerts.append({
                    "alert_id": f"ALT-{uuid.uuid4().hex[:8].upper()}",
                    "timestamp": now_str,
                    "resource": f"Disk ({mount})",
                    "metric_name": "utilization_percent",
                    "observed_value": dpct,
                    "threshold_value": disk_warn,
                    "severity": AlertSeverity.HIGH,
                    "message": f"Disk partition {mount} usage reached {dpct:.1f}% (warning: {disk_warn:.1f}%)",
                    "status": AlertStatus.ACTIVE
                })

        # Persist generated alerts
        for alert in generated_alerts:
            self._record_alert(alert)

        return generated_alerts

    def _record_alert(self, alert: Dict[str, Any]) -> None:
        """Write alert to structured log file and JSON storage."""
        # Append to human-readable alerts.log
        log_line = (
            f"[{alert['timestamp']}] [{alert['severity']}] "
            f"Resource: {alert['resource']} | "
            f"Observed: {alert['observed_value']} | "
            f"Threshold: {alert['threshold_value']} | "
            f"Message: {alert['message']}\n"
        )
        try:
            with open(self.alerts_log_path, "a", encoding="utf-8") as f:
                f.write(log_line)
        except Exception as e:
            logger.error(f"Failed writing to alerts log {self.alerts_log_path}: {e}")

        # Update JSON alerts database
        try:
            alerts = self.get_all_alerts()
            alerts.append(alert)
            with open(self.alerts_data_path, "w", encoding="utf-8") as f:
                json.dump(alerts, f, indent=2)
        except Exception as e:
            logger.error(f"Failed updating alerts data {self.alerts_data_path}: {e}")

    def get_all_alerts(self) -> List[Dict[str, Any]]:
        """Retrieve all stored alerts."""
        if not os.path.exists(self.alerts_data_path):
            return []
        try:
            with open(self.alerts_data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"Error reading alerts from {self.alerts_data_path}: {e}")
            return []

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Retrieve only active alerts."""
        return [a for a in self.get_all_alerts() if a.get("status") == AlertStatus.ACTIVE]

    def resolve_alert(self, alert_id: str, notes: str = "") -> bool:
        """Mark an alert as resolved."""
        alerts = self.get_all_alerts()
        updated = False
        for a in alerts:
            if a.get("alert_id") == alert_id:
                a["status"] = AlertStatus.RESOLVED
                a["resolved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if notes:
                    a["resolution_notes"] = notes
                updated = True
                break
        if updated:
            try:
                with open(self.alerts_data_path, "w", encoding="utf-8") as f:
                    json.dump(alerts, f, indent=2)
                return True
            except Exception as e:
                logger.error(f"Error saving resolved alert: {e}")
        return False

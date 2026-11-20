"""
ServerWatch Test Suite Runner
Runs unit tests for metrics collection, alert evaluation, and incident management.
"""

import sys
import unittest
import os

# Ensure current directory is in path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from monitoring.metrics import SystemMetricsCollector, bytes_to_human, load_config
from monitoring.alerts import AlertEngine, AlertSeverity, AlertStatus
from incident_management.incident_manager import IncidentManager, IncidentSeverity, IncidentStatus, IncidentCategory
from incident_management.report_generator import ReportGenerator


class TestMetricsCollector(unittest.TestCase):
    def setUp(self):
        self.collector = SystemMetricsCollector("config/settings.json")

    def test_bytes_to_human(self):
        self.assertEqual(bytes_to_human(0), "0 B")
        self.assertEqual(bytes_to_human(1024), "1.00 KB")
        self.assertEqual(bytes_to_human(1024 * 1024), "1.00 MB")
        self.assertEqual(bytes_to_human(1024 * 1024 * 1024), "1.00 GB")

    def test_load_config(self):
        cfg = load_config("config/settings.json")
        self.assertIn("thresholds", cfg)
        self.assertEqual(cfg["thresholds"]["cpu_critical_percent"], 80.0)

    def test_system_info(self):
        info = self.collector.get_system_info()
        self.assertIn("hostname", info)
        self.assertIn("os_name", info)
        self.assertIn("uptime_human", info)
        self.assertGreaterEqual(info["uptime_seconds"], 0)

    def test_cpu_metrics(self):
        cpu = self.collector.get_cpu_metrics()
        self.assertIn("utilization_percent", cpu)
        self.assertTrue(0.0 <= cpu["utilization_percent"] <= 100.0)
        self.assertGreaterEqual(cpu["logical_cores"], 1)

    def test_memory_metrics(self):
        mem = self.collector.get_memory_metrics()
        self.assertIn("total_bytes", mem)
        self.assertGreater(mem["total_bytes"], 0)
        self.assertTrue(0.0 <= mem["utilization_percent"] <= 100.0)

    def test_disk_metrics(self):
        disk = self.collector.get_disk_metrics()
        self.assertIn("partitions", disk)
        self.assertGreater(len(disk["partitions"]), 0)

    def test_network_metrics(self):
        net = self.collector.get_network_metrics()
        self.assertIn("bytes_sent_total", net)
        self.assertIn("interfaces", net)
        self.assertIsInstance(net["interfaces"], list)

    def test_snapshot_record(self):
        test_path = "logs/test_metrics_runner.jsonl"
        self.collector.metrics_log_path = test_path
        snapshot = self.collector.record_snapshot()
        self.assertIn("timestamp", snapshot)
        self.assertTrue(os.path.exists(test_path))
        # cleanup
        if os.path.exists(test_path):
            os.remove(test_path)


class TestAlertEngine(unittest.TestCase):
    def setUp(self):
        self.engine = AlertEngine("config/settings.json")
        self.engine.alerts_log_path = "logs/test_alerts.log"
        self.engine.alerts_data_path = "logs/test_alerts.json"
        self.engine._ensure_paths()

    def tearDown(self):
        for p in ["logs/test_alerts.log", "logs/test_alerts.json"]:
            if os.path.exists(p):
                os.remove(p)

    def test_normal_metrics_produce_no_alerts(self):
        mock_snapshot = {
            "cpu": {"utilization_percent": 25.0, "load_ratio_1m": 0.3},
            "memory": {"utilization_percent": 40.0},
            "disk": {"partitions": [{"mountpoint": "/", "utilization_percent": 50.0}]}
        }
        alerts = self.engine.evaluate(mock_snapshot)
        self.assertEqual(len(alerts), 0)

    def test_critical_cpu_alert(self):
        mock_snapshot = {
            "cpu": {"utilization_percent": 88.5, "load_ratio_1m": 0.5},
            "memory": {"utilization_percent": 40.0},
            "disk": {"partitions": [{"mountpoint": "/", "utilization_percent": 50.0}]}
        }
        alerts = self.engine.evaluate(mock_snapshot)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["resource"], "CPU")
        self.assertEqual(alerts[0]["severity"], AlertSeverity.CRITICAL)

    def test_critical_disk_alert(self):
        mock_snapshot = {
            "cpu": {"utilization_percent": 15.0, "load_ratio_1m": 0.2},
            "memory": {"utilization_percent": 50.0},
            "disk": {"partitions": [{"mountpoint": "/var", "utilization_percent": 91.0}]}
        }
        alerts = self.engine.evaluate(mock_snapshot)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["resource"], "Disk (/var)")
        self.assertEqual(alerts[0]["severity"], AlertSeverity.CRITICAL)

    def test_resolve_alert(self):
        mock_snapshot = {
            "cpu": {"utilization_percent": 90.0, "load_ratio_1m": 2.8},
            "memory": {"utilization_percent": 88.0},
            "disk": {"partitions": []}
        }
        alerts = self.engine.evaluate(mock_snapshot)
        self.assertGreaterEqual(len(alerts), 2)
        target_id = alerts[0]["alert_id"]
        res = self.engine.resolve_alert(target_id, "Mitigated")
        self.assertTrue(res)


class TestIncidentManager(unittest.TestCase):
    def setUp(self):
        self.test_file = "logs/test_incidents_runner.json"
        self.manager = IncidentManager(self.test_file)

    def tearDown(self):
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    def test_create_and_deduplicate(self):
        inc1 = self.manager.create_incident(
            category=IncidentCategory.RESOURCE_EXHAUSTION,
            severity=IncidentSeverity.CRITICAL,
            description="CPU load peaked at 95%",
            affected_resource="CPU"
        )
        self.assertTrue(inc1["incident_id"].startswith("INC-"))

        # Deduplicate active
        inc2 = self.manager.create_incident(
            category=IncidentCategory.RESOURCE_EXHAUSTION,
            severity=IncidentSeverity.CRITICAL,
            description="CPU load peaked at 97%",
            affected_resource="CPU"
        )
        self.assertEqual(inc1["incident_id"], inc2["incident_id"])
        self.assertEqual(inc2["occurrence_count"], 2)

    def test_status_update(self):
        inc = self.manager.create_incident(
            category=IncidentCategory.SERVICE_FAILURE,
            severity=IncidentSeverity.HIGH,
            description="Daemon stopped",
            affected_resource="Service (cron)"
        )
        updated = self.manager.update_incident_status(
            inc["incident_id"],
            IncidentStatus.RESOLVED,
            "Restarted daemon"
        )
        self.assertEqual(updated["status"], IncidentStatus.RESOLVED)
        self.assertIsNotNone(updated["resolved_at"])

    def test_report_generation(self):
        generator = ReportGenerator("reports/test_reports")
        rep = generator.generate_health_report()
        self.assertTrue(os.path.exists(rep["markdown_path"]))
        self.assertTrue(os.path.exists(rep["json_path"]))
        csv_file = generator.export_incidents_csv()
        self.assertTrue(os.path.exists(csv_file))


if __name__ == "__main__":
    unittest.main(verbosity=2)

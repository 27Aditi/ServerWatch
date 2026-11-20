"""Unit tests for ServerWatch Alert Engine."""

import os
import pytest
from monitoring.alerts import AlertEngine, AlertSeverity, AlertStatus


@pytest.fixture
def temp_alert_engine(tmp_path):
    engine = AlertEngine("config/settings.json")
    engine.alerts_log_path = str(tmp_path / "test_alerts.log")
    engine.alerts_data_path = str(tmp_path / "test_alerts.json")
    engine._ensure_paths()
    return engine


def test_normal_metrics_produce_no_alerts(temp_alert_engine):
    mock_snapshot = {
        "cpu": {"utilization_percent": 25.0, "load_ratio_1m": 0.3},
        "memory": {"utilization_percent": 40.0},
        "disk": {"partitions": [{"mountpoint": "/", "utilization_percent": 50.0}]}
    }
    alerts = temp_alert_engine.evaluate(mock_snapshot)
    assert len(alerts) == 0


def test_critical_cpu_alert(temp_alert_engine):
    mock_snapshot = {
        "cpu": {"utilization_percent": 88.5, "load_ratio_1m": 0.5},
        "memory": {"utilization_percent": 40.0},
        "disk": {"partitions": [{"mountpoint": "/", "utilization_percent": 50.0}]}
    }
    alerts = temp_alert_engine.evaluate(mock_snapshot)
    assert len(alerts) == 1
    assert alerts[0]["resource"] == "CPU"
    assert alerts[0]["severity"] == AlertSeverity.CRITICAL
    assert alerts[0]["observed_value"] == 88.5


def test_high_memory_alert(temp_alert_engine):
    mock_snapshot = {
        "cpu": {"utilization_percent": 10.0, "load_ratio_1m": 0.1},
        "memory": {"utilization_percent": 86.0},
        "disk": {"partitions": [{"mountpoint": "/", "utilization_percent": 40.0}]}
    }
    alerts = temp_alert_engine.evaluate(mock_snapshot)
    assert len(alerts) == 1
    assert alerts[0]["resource"] == "RAM"
    assert alerts[0]["severity"] == AlertSeverity.CRITICAL


def test_critical_disk_alert(temp_alert_engine):
    mock_snapshot = {
        "cpu": {"utilization_percent": 15.0, "load_ratio_1m": 0.2},
        "memory": {"utilization_percent": 50.0},
        "disk": {"partitions": [
            {"mountpoint": "/var", "utilization_percent": 92.0},
            {"mountpoint": "/home", "utilization_percent": 30.0}
        ]}
    }
    alerts = temp_alert_engine.evaluate(mock_snapshot)
    assert len(alerts) == 1
    assert alerts[0]["resource"] == "Disk (/var)"
    assert alerts[0]["severity"] == AlertSeverity.CRITICAL


def test_alert_resolution_workflow(temp_alert_engine):
    mock_snapshot = {
        "cpu": {"utilization_percent": 95.0, "load_ratio_1m": 3.0},
        "memory": {"utilization_percent": 90.0},
        "disk": {"partitions": []}
    }
    alerts = temp_alert_engine.evaluate(mock_snapshot)
    assert len(alerts) >= 2
    first_alert_id = alerts[0]["alert_id"]

    # Verify active alerts count
    active = temp_alert_engine.get_active_alerts()
    assert len(active) == len(alerts)

    # Resolve first alert
    success = temp_alert_engine.resolve_alert(first_alert_id, notes="Operator cleared runaway compute process.")
    assert success is True

    # Check active alerts decreased
    active_after = temp_alert_engine.get_active_alerts()
    assert len(active_after) == len(alerts) - 1

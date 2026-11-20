"""Unit tests for ServerWatch System Metrics Collector."""

import os
import pytest
from monitoring.metrics import SystemMetricsCollector, bytes_to_human, load_config


def test_bytes_to_human():
    assert bytes_to_human(0) == "0 B"
    assert bytes_to_human(1024) == "1.00 KB"
    assert bytes_to_human(1024 * 1024) == "1.00 MB"
    assert bytes_to_human(1024 * 1024 * 1024) == "1.00 GB"
    assert bytes_to_human(1536 * 1024 * 1024) == "1.50 GB"


def test_load_config():
    config = load_config("config/settings.json")
    assert "thresholds" in config
    assert "cpu_critical_percent" in config["thresholds"]
    assert config["thresholds"]["cpu_critical_percent"] == 80.0


def test_system_info():
    collector = SystemMetricsCollector("config/settings.json")
    info = collector.get_system_info()
    assert "hostname" in info
    assert "os_name" in info
    assert "uptime_seconds" in info
    assert "uptime_human" in info
    assert info["uptime_seconds"] >= 0


def test_cpu_metrics():
    collector = SystemMetricsCollector("config/settings.json")
    cpu = collector.get_cpu_metrics()
    assert "utilization_percent" in cpu
    assert 0.0 <= cpu["utilization_percent"] <= 100.0
    assert cpu["logical_cores"] >= 1
    assert "load_1m" in cpu


def test_memory_metrics():
    collector = SystemMetricsCollector("config/settings.json")
    mem = collector.get_memory_metrics()
    assert "total_bytes" in mem
    assert mem["total_bytes"] > 0
    assert "available_bytes" in mem
    assert 0.0 <= mem["utilization_percent"] <= 100.0


def test_disk_metrics():
    collector = SystemMetricsCollector("config/settings.json")
    disk = collector.get_disk_metrics()
    assert "partitions" in disk
    assert len(disk["partitions"]) > 0
    first_part = disk["partitions"][0]
    assert "mountpoint" in first_part
    assert "utilization_percent" in first_part


def test_network_metrics():
    collector = SystemMetricsCollector("config/settings.json")
    net = collector.get_network_metrics()
    assert "bytes_sent_total" in net
    assert "bytes_recv_total" in net
    assert "interfaces" in net
    assert isinstance(net["interfaces"], list)


def test_snapshot_and_history(tmp_path):
    collector = SystemMetricsCollector("config/settings.json")
    test_log = str(tmp_path / "test_metrics.jsonl")
    collector.metrics_log_path = test_log

    snapshot = collector.record_snapshot()
    assert "timestamp" in snapshot
    assert "cpu" in snapshot
    assert "memory" in snapshot
    assert os.path.exists(test_log)

    history = collector.get_history(limit=10)
    assert len(history) == 1
    assert history[0]["timestamp"] == snapshot["timestamp"]

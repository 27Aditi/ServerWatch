"""Unit tests for ServerWatch Incident Manager and Report Generator."""

import os
import pytest
from incident_management.incident_manager import IncidentManager, IncidentSeverity, IncidentStatus, IncidentCategory
from incident_management.report_generator import ReportGenerator


@pytest.fixture
def temp_incident_manager(tmp_path):
    storage_path = str(tmp_path / "test_incidents.json")
    manager = IncidentManager(storage_path)
    return manager


def test_create_and_fetch_incident(temp_incident_manager):
    inc = temp_incident_manager.create_incident(
        category=IncidentCategory.RESOURCE_EXHAUSTION,
        severity=IncidentSeverity.CRITICAL,
        description="CPU spiked to 98% under high load",
        affected_resource="CPU"
    )

    assert "incident_id" in inc
    assert inc["incident_id"].startswith("INC-")
    assert inc["severity"] == IncidentSeverity.CRITICAL
    assert inc["status"] == IncidentStatus.ACTIVE

    all_incidents = temp_incident_manager.get_incidents()
    assert len(all_incidents) == 1


def test_incident_deduplication(temp_incident_manager):
    inc1 = temp_incident_manager.create_incident(
        category=IncidentCategory.DISK_PRESSURE,
        severity=IncidentSeverity.HIGH,
        description="Disk partition / reached 86%",
        affected_resource="Disk (/)"
    )

    inc2 = temp_incident_manager.create_incident(
        category=IncidentCategory.DISK_PRESSURE,
        severity=IncidentSeverity.HIGH,
        description="Disk partition / reached 87%",
        affected_resource="Disk (/)"
    )

    # Should update existing incident rather than duplicating
    assert inc1["incident_id"] == inc2["incident_id"]
    all_incidents = temp_incident_manager.get_incidents()
    assert len(all_incidents) == 1
    assert all_incidents[0]["occurrence_count"] == 2


def test_incident_status_update(temp_incident_manager):
    inc = temp_incident_manager.create_incident(
        category=IncidentCategory.SERVICE_FAILURE,
        severity=IncidentSeverity.CRITICAL,
        description="Nginx web server is inactive",
        affected_resource="Service (nginx)"
    )

    updated = temp_incident_manager.update_incident_status(
        incident_id=inc["incident_id"],
        new_status=IncidentStatus.RESOLVED,
        resolution_notes="Restarted nginx via systemctl after renewing SSL cert."
    )

    assert updated is not None
    assert updated["status"] == IncidentStatus.RESOLVED
    assert updated["resolution"] == "Restarted nginx via systemctl after renewing SSL cert."
    assert updated["resolved_at"] is not None


def test_report_generation(tmp_path):
    generator = ReportGenerator(reports_dir=str(tmp_path / "reports"))
    report = generator.generate_health_report()

    assert os.path.exists(report["markdown_path"])
    assert os.path.exists(report["json_path"])
    assert "ServerWatch Health & Infrastructure Report" in report["content"]

    csv_path = generator.export_incidents_csv()
    assert os.path.exists(csv_path)

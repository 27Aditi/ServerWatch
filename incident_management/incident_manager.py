"""
ServerWatch - Incident Management Module
Provides enterprise-grade incident tracking, lifecycle management,
severity indexing, filtering, and resolution workflows.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger("serverwatch.incidents")


class IncidentSeverity:
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentStatus:
    ACTIVE = "ACTIVE"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class IncidentCategory:
    RESOURCE_EXHAUSTION = "RESOURCE_EXHAUSTION"
    SERVICE_FAILURE = "SERVICE_FAILURE"
    DISK_PRESSURE = "DISK_PRESSURE"
    HIGH_LOAD = "HIGH_LOAD"
    SECURITY = "SECURITY"
    SYSTEM = "SYSTEM"


class IncidentManager:
    """Manages the full lifecycle of system and infrastructure incidents."""

    def __init__(self, storage_path: str = "logs/incidents.json"):
        self.storage_path = storage_path
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        directory = os.path.dirname(self.storage_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        if not os.path.exists(self.storage_path):
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump([], f)

    def _load_incidents(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.storage_path):
            return []
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"Failed to load incidents from {self.storage_path}: {e}")
            return []

    def _save_incidents(self, incidents: List[Dict[str, Any]]) -> bool:
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(incidents, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save incidents to {self.storage_path}: {e}")
            return False

    def generate_incident_id(self) -> str:
        """Generate human-readable sequential ID: INC-YYYYMMDD-XXXX."""
        date_str = datetime.now().strftime("%Y%m%d")
        incidents = self._load_incidents()
        count_today = sum(1 for inc in incidents if inc.get("incident_id", "").startswith(f"INC-{date_str}"))
        return f"INC-{date_str}-{count_today + 1:04d}"

    def create_incident(
        self,
        category: str,
        severity: str,
        description: str,
        affected_resource: str,
        notes: str = "",
        auto_deduplicate: bool = True
    ) -> Dict[str, Any]:
        """
        Record a new incident. If auto_deduplicate is True, will not duplicate
        an existing ACTIVE incident with the same category and affected_resource.
        """
        incidents = self._load_incidents()

        if auto_deduplicate:
            for inc in incidents:
                if (inc.get("status") in [IncidentStatus.ACTIVE, IncidentStatus.INVESTIGATING]
                        and inc.get("category") == category
                        and inc.get("affected_resource") == affected_resource):
                    # Update timestamp and notes instead of spamming duplicates
                    inc["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    inc["occurrence_count"] = inc.get("occurrence_count", 1) + 1
                    self._save_incidents(incidents)
                    return inc

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        incident = {
            "incident_id": self.generate_incident_id(),
            "timestamp": now_str,
            "last_seen": now_str,
            "category": category,
            "severity": severity,
            "description": description,
            "affected_resource": affected_resource,
            "status": IncidentStatus.ACTIVE,
            "occurrence_count": 1,
            "notes": notes,
            "resolution": "",
            "resolved_at": None
        }

        incidents.insert(0, incident)
        self._save_incidents(incidents)
        logger.warning(f"New incident created: {incident['incident_id']} [{severity}] {description}")
        return incident

    def update_incident_status(
        self,
        incident_id: str,
        new_status: str,
        resolution_notes: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Update incident workflow state and resolution comments."""
        incidents = self._load_incidents()
        target = None
        for inc in incidents:
            if inc.get("incident_id") == incident_id:
                inc["status"] = new_status
                if new_status in [IncidentStatus.RESOLVED, IncidentStatus.FALSE_POSITIVE]:
                    inc["resolved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    inc["resolution"] = resolution_notes
                target = inc
                break

        if target:
            self._save_incidents(incidents)
        return target

    def get_incidents(
        self,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Filter incidents by severity, lifecycle status, and date range."""
        incidents = self._load_incidents()
        filtered = incidents

        if severity and severity != "ALL":
            filtered = [i for i in filtered if i.get("severity") == severity]

        if status and status != "ALL":
            filtered = [i for i in filtered if i.get("status") == status]

        if date_from:
            filtered = [i for i in filtered if i.get("timestamp", "")[:10] >= date_from]

        if date_to:
            filtered = [i for i in filtered if i.get("timestamp", "")[:10] <= date_to]

        return filtered

    def get_statistics(self) -> Dict[str, Any]:
        """Compute incident summary metrics."""
        incidents = self._load_incidents()
        stats = {
            "total": len(incidents),
            "active": sum(1 for i in incidents if i.get("status") == IncidentStatus.ACTIVE),
            "investigating": sum(1 for i in incidents if i.get("status") == IncidentStatus.INVESTIGATING),
            "resolved": sum(1 for i in incidents if i.get("status") == IncidentStatus.RESOLVED),
            "false_positive": sum(1 for i in incidents if i.get("status") == IncidentStatus.FALSE_POSITIVE),
            "critical": sum(1 for i in incidents if i.get("severity") == IncidentSeverity.CRITICAL),
            "high": sum(1 for i in incidents if i.get("severity") == IncidentSeverity.HIGH),
            "medium": sum(1 for i in incidents if i.get("severity") == IncidentSeverity.MEDIUM),
            "low": sum(1 for i in incidents if i.get("severity") == IncidentSeverity.LOW)
        }
        return stats

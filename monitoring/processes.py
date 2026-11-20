"""
ServerWatch - Process Management and Inspection Module
Provides comprehensive process listing, top consumer extraction,
resource breakdown, and audited process termination.
"""

import os
import sys
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
import psutil

logger = logging.getLogger("serverwatch.processes")


def bytes_to_human(n_bytes: int) -> str:
    if n_bytes is None or n_bytes < 0:
        return "0 B"
    symbols = ('B', 'KB', 'MB', 'GB', 'TB')
    prefix = {}
    for i, s in enumerate(symbols):
        prefix[s] = 1 << (i * 10)
    for s in reversed(symbols):
        if n_bytes >= prefix[s]:
            value = float(n_bytes) / prefix[s]
            return f"{value:.2f} {s}"
    return f"{n_bytes} B"


class ProcessManager:
    """Safely inspects and monitors host processes."""

    def __init__(self, audit_log_path: str = "logs/process_audit.log"):
        self.audit_log_path = audit_log_path
        self._ensure_log_dir()

    def _ensure_log_dir(self) -> None:
        log_dir = os.path.dirname(self.audit_log_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

    def get_process_summary(self) -> Dict[str, int]:
        """Return counts of processes grouped by state."""
        counts = {
            "total": 0,
            "running": 0,
            "sleeping": 0,
            "idle": 0,
            "stopped": 0,
            "zombie": 0,
            "other": 0
        }
        for proc in psutil.process_iter(['status']):
            try:
                counts["total"] += 1
                status = proc.info.get('status')
                if status == psutil.STATUS_RUNNING:
                    counts["running"] += 1
                elif status == psutil.STATUS_SLEEPING:
                    counts["sleeping"] += 1
                elif status == psutil.STATUS_IDLE:
                    counts["idle"] += 1
                elif status == psutil.STATUS_STOPPED:
                    counts["stopped"] += 1
                elif status == psutil.STATUS_ZOMBIE:
                    counts["zombie"] += 1
                else:
                    counts["other"] += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return counts

    def get_all_processes(self, limit: int = 150) -> List[Dict[str, Any]]:
        """List running processes with resource consumption details."""
        processes: List[Dict[str, Any]] = []
        attrs = ['pid', 'name', 'username', 'status', 'cpu_percent', 'memory_percent', 'memory_info', 'create_time', 'num_threads']

        for proc in psutil.process_iter(attrs):
            try:
                pinfo = proc.info
                mem_rss = pinfo['memory_info'].rss if pinfo.get('memory_info') else 0
                create_dt = datetime.fromtimestamp(pinfo['create_time']).strftime('%Y-%m-%d %H:%M:%S') if pinfo.get('create_time') else "N/A"

                processes.append({
                    "pid": pinfo['pid'],
                    "name": pinfo['name'] or "unknown",
                    "username": pinfo['username'] or "unknown",
                    "status": pinfo['status'] or "unknown",
                    "cpu_percent": round(pinfo.get('cpu_percent') or 0.0, 1),
                    "memory_percent": round(pinfo.get('memory_percent') or 0.0, 2),
                    "memory_rss_bytes": mem_rss,
                    "memory_rss_human": bytes_to_human(mem_rss),
                    "create_time": create_dt,
                    "threads": pinfo.get('num_threads') or 1
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        # Sort by CPU usage descending by default
        processes.sort(key=lambda x: x["cpu_percent"], reverse=True)
        return processes[:limit]

    def get_top_cpu_processes(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve top CPU consuming processes."""
        procs = self.get_all_processes(limit=250)
        procs.sort(key=lambda x: x["cpu_percent"], reverse=True)
        return procs[:limit]

    def get_top_memory_processes(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve top memory consuming processes."""
        procs = self.get_all_processes(limit=250)
        procs.sort(key=lambda x: x["memory_rss_bytes"], reverse=True)
        return procs[:limit]

    def get_process_by_pid(self, pid: int) -> Optional[Dict[str, Any]]:
        """Fetch detailed information for a single process."""
        try:
            p = psutil.Process(pid)
            with p.oneshot():
                mem_info = p.memory_info()
                return {
                    "pid": p.pid,
                    "name": p.name(),
                    "exe": p.exe() if hasattr(p, "exe") else "N/A",
                    "cwd": p.cwd() if hasattr(p, "cwd") else "N/A",
                    "cmdline": " ".join(p.cmdline()) if p.cmdline() else p.name(),
                    "username": p.username(),
                    "status": p.status(),
                    "cpu_percent": round(p.cpu_percent(), 1),
                    "memory_percent": round(p.memory_percent(), 2),
                    "memory_rss_human": bytes_to_human(mem_info.rss),
                    "num_threads": p.num_threads(),
                    "create_time": datetime.fromtimestamp(p.create_time()).strftime('%Y-%m-%d %H:%M:%S')
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.warning(f"Could not inspect PID {pid}: {e}")
            return None

    def terminate_process_safely(self, pid: int, user_confirmed: bool = False, reason: str = "") -> Dict[str, Any]:
        """
        Safely terminate a process ONLY when explicit user confirmation is passed.
        Protects system-critical processes (PID 1, init, systemd, etc.).
        """
        if not user_confirmed:
            return {
                "success": False,
                "message": "Termination refused: Explicit user confirmation is required."
            }

        # Guard against terminating critical system processes
        if pid <= 1:
            return {
                "success": False,
                "message": f"Termination blocked: PID {pid} is a protected core system process."
            }

        try:
            proc = psutil.Process(pid)
            proc_name = proc.name()
            protected_names = ["systemd", "init", "kthreadd", "svchost.exe", "csrss.exe", "lsass.exe"]
            if proc_name.lower() in protected_names:
                return {
                    "success": False,
                    "message": f"Termination blocked: {proc_name} is protected infrastructure."
                }

            # Attempt graceful SIGTERM first
            proc.terminate()
            gone, alive = psutil.wait_procs([proc], timeout=3)
            if alive:
                # Force SIGKILL if not exited
                proc.kill()

            audit_entry = (
                f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                f"PROCESS_TERMINATED | PID: {pid} | Name: {proc_name} | Reason: {reason or 'Manual operator action'}\n"
            )
            try:
                with open(self.audit_log_path, "a", encoding="utf-8") as f:
                    f.write(audit_entry)
            except Exception:
                pass

            return {
                "success": True,
                "message": f"Process {proc_name} (PID {pid}) was safely terminated."
            }

        except psutil.NoSuchProcess:
            return {"success": False, "message": f"Process {pid} no longer exists."}
        except psutil.AccessDenied:
            return {"success": False, "message": f"Permission denied terminating PID {pid}. Elevated privileges required."}
        except Exception as e:
            return {"success": False, "message": f"Failed to terminate PID {pid}: {str(e)}"}

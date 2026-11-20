"""
ServerWatch - System Health Monitoring Module
Collects real-time hardware, operating system, and network metrics
using psutil and standard Linux system interfaces.
"""

import os
import sys
import json
import time
import socket
import platform
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import psutil

# Setup module logger
logger = logging.getLogger("serverwatch.metrics")


def load_config(config_path: str = "config/settings.json") -> Dict[str, Any]:
    """Load configuration from JSON file or return sensible defaults."""
    default_config = {
        "system": {
            "collection_interval_seconds": 5,
            "history_retention_points": 60,
            "log_level": "INFO"
        },
        "thresholds": {
            "cpu_warning_percent": 70.0,
            "cpu_critical_percent": 80.0,
            "memory_warning_percent": 75.0,
            "memory_critical_percent": 85.0,
            "disk_warning_percent": 75.0,
            "disk_critical_percent": 85.0,
            "load_warning_ratio": 1.5,
            "load_critical_ratio": 2.5
        },
        "paths": {
            "logs_dir": "logs",
            "metrics_log": "logs/metrics.jsonl",
            "alerts_log": "logs/alerts.log",
            "incidents_file": "logs/incidents.json",
            "app_log": "logs/serverwatch.log"
        }
    }

    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                # Merge loaded with defaults
                for k, v in loaded.items():
                    if isinstance(v, dict) and k in default_config:
                        default_config[k].update(v)
                    else:
                        default_config[k] = v
        except Exception as e:
            logger.warning(f"Failed to read {config_path}: {e}. Using default config.")
    return default_config


def bytes_to_human(n_bytes: int) -> str:
    """Convert bytes to human-readable string (e.g., 1024 -> 1.00 KB)."""
    if n_bytes is None or n_bytes < 0:
        return "0 B"
    symbols = ('B', 'KB', 'MB', 'GB', 'TB', 'PB')
    prefix = {}
    for i, s in enumerate(symbols):
        prefix[s] = 1 << (i * 10)
    for s in reversed(symbols):
        if n_bytes >= prefix[s]:
            value = float(n_bytes) / prefix[s]
            return f"{value:.2f} {s}"
    return f"{n_bytes} B"


class SystemMetricsCollector:
    """Collects real-time and historical Linux / host system performance metrics."""

    def __init__(self, config_path: str = "config/settings.json"):
        self.config = load_config(config_path)
        self.metrics_log_path = self.config.get("paths", {}).get("metrics_log", "logs/metrics.jsonl")
        self._ensure_log_dirs()
        self._last_net_io = psutil.net_io_counters()
        self._last_net_time = time.time()

    def _ensure_log_dirs(self) -> None:
        """Ensure destination directories exist."""
        log_dir = os.path.dirname(self.metrics_log_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

    def get_system_info(self) -> Dict[str, Any]:
        """Collect host operating system and hardware metadata."""
        boot_timestamp = psutil.boot_time()
        boot_dt = datetime.fromtimestamp(boot_timestamp)
        uptime_delta = datetime.now() - boot_dt
        days = uptime_delta.days
        hours, remainder = divmod(uptime_delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"

        # Read Linux distribution info if available
        distro_name = "Linux"
        if hasattr(platform, "freedesktop_os_release"):
            try:
                os_release = platform.freedesktop_os_release()
                distro_name = os_release.get("PRETTY_NAME", platform.system())
            except Exception:
                distro_name = platform.system()
        elif os.path.exists("/etc/os-release"):
            try:
                with open("/etc/os-release", "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("PRETTY_NAME="):
                            distro_name = line.split("=")[1].strip().strip('"')
                            break
            except Exception:
                distro_name = platform.system()
        else:
            distro_name = f"{platform.system()} {platform.release()}"

        return {
            "hostname": platform.node(),
            "os_name": platform.system(),
            "os_version": platform.version(),
            "kernel_release": platform.release(),
            "architecture": platform.machine(),
            "processor": platform.processor() or platform.machine(),
            "distro": distro_name,
            "boot_time": boot_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "uptime_seconds": int(uptime_delta.total_seconds()),
            "uptime_human": uptime_str,
            "python_version": platform.python_version()
        }

    def get_cpu_metrics(self) -> Dict[str, Any]:
        """Collect CPU utilization, core count, frequencies, and load average."""
        cpu_percent = psutil.cpu_percent(interval=None)
        cpu_percent_per_core = psutil.cpu_percent(interval=None, percpu=True)
        cpu_count_logical = psutil.cpu_count(logical=True) or 1
        cpu_count_physical = psutil.cpu_count(logical=False) or cpu_count_logical

        freq = psutil.cpu_freq()
        cpu_freq_current = round(freq.current, 2) if freq else 0.0
        cpu_freq_max = round(freq.max, 2) if freq and freq.max else 0.0

        # Load average (1m, 5m, 15m)
        load_1, load_5, load_15 = (0.0, 0.0, 0.0)
        if hasattr(os, "getloadavg"):
            try:
                load_1, load_5, load_15 = os.getloadavg()
            except Exception as e:
                logger.debug(f"Could not get os.getloadavg: {e}")
        elif hasattr(psutil, "getloadavg"):
            try:
                load_1, load_5, load_15 = psutil.getloadavg()
            except Exception as e:
                logger.debug(f"Could not get psutil.getloadavg: {e}")
        else:
            # Fallback estimation for environments where getloadavg is unsupported
            load_1 = round(cpu_percent / 100.0 * cpu_count_logical, 2)
            load_5 = load_1
            load_15 = load_1

        return {
            "utilization_percent": round(cpu_percent, 2),
            "per_core_percent": [round(c, 2) for c in cpu_percent_per_core],
            "logical_cores": cpu_count_logical,
            "physical_cores": cpu_count_physical,
            "frequency_mhz": cpu_freq_current,
            "frequency_max_mhz": cpu_freq_max,
            "load_1m": round(load_1, 2),
            "load_5m": round(load_5, 2),
            "load_15m": round(load_15, 2),
            "load_ratio_1m": round(load_1 / cpu_count_logical, 2)
        }

    def get_memory_metrics(self) -> Dict[str, Any]:
        """Collect RAM and Swap space metrics."""
        vmem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        # Buffers and cached are present on Linux
        cached_bytes = getattr(vmem, "cached", 0)
        buffers_bytes = getattr(vmem, "buffers", 0)

        return {
            "total_bytes": vmem.total,
            "available_bytes": vmem.available,
            "used_bytes": vmem.used,
            "free_bytes": vmem.free,
            "utilization_percent": round(vmem.percent, 2),
            "total_human": bytes_to_human(vmem.total),
            "available_human": bytes_to_human(vmem.available),
            "used_human": bytes_to_human(vmem.used),
            "free_human": bytes_to_human(vmem.free),
            "cached_human": bytes_to_human(cached_bytes),
            "buffers_human": bytes_to_human(buffers_bytes),
            "swap_total_bytes": swap.total,
            "swap_used_bytes": swap.used,
            "swap_free_bytes": swap.free,
            "swap_percent": round(swap.percent, 2),
            "swap_total_human": bytes_to_human(swap.total),
            "swap_used_human": bytes_to_human(swap.used)
        }

    def get_disk_metrics(self) -> Dict[str, Any]:
        """Collect filesystem partition metrics and I/O counters."""
        partitions = []
        max_utilization = 0.0

        for part in psutil.disk_partitions(all=False):
            # Filter pseudo-filesystems on Linux
            if os.name != "nt":
                if part.fstype in ("squashfs", "tmpfs", "devtmpfs", "overlay", "iso9660") or part.mountpoint.startswith("/snap"):
                    continue
            try:
                usage = psutil.disk_usage(part.mountpoint)
                pct = round(usage.percent, 2)
                if pct > max_utilization:
                    max_utilization = pct
                partitions.append({
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "total_bytes": usage.total,
                    "used_bytes": usage.used,
                    "free_bytes": usage.free,
                    "utilization_percent": pct,
                    "total_human": bytes_to_human(usage.total),
                    "used_human": bytes_to_human(usage.used),
                    "free_human": bytes_to_human(usage.free)
                })
            except (PermissionError, OSError):
                continue

        # Disk I/O counters
        io_counters = psutil.disk_io_counters()
        io_dict = {
            "read_bytes": io_counters.read_bytes if io_counters else 0,
            "write_bytes": io_counters.write_bytes if io_counters else 0,
            "read_human": bytes_to_human(io_counters.read_bytes) if io_counters else "0 B",
            "write_human": bytes_to_human(io_counters.write_bytes) if io_counters else "0 B",
            "read_count": io_counters.read_count if io_counters else 0,
            "write_count": io_counters.write_count if io_counters else 0
        }

        # Fallback root partition if partitions list is empty
        if not partitions:
            try:
                root_usage = psutil.disk_usage(os.path.abspath(os.sep))
                partitions.append({
                    "device": os.path.abspath(os.sep),
                    "mountpoint": os.path.abspath(os.sep),
                    "fstype": "standard",
                    "total_bytes": root_usage.total,
                    "used_bytes": root_usage.used,
                    "free_bytes": root_usage.free,
                    "utilization_percent": round(root_usage.percent, 2),
                    "total_human": bytes_to_human(root_usage.total),
                    "used_human": bytes_to_human(root_usage.used),
                    "free_human": bytes_to_human(root_usage.free)
                })
                max_utilization = round(root_usage.percent, 2)
            except Exception:
                pass

        return {
            "partitions": partitions,
            "max_utilization_percent": max_utilization,
            "io": io_dict
        }

    def get_network_metrics(self) -> Dict[str, Any]:
        """Collect network interface stats and transfer rate deltas."""
        now = time.time()
        curr_net = psutil.net_io_counters()
        elapsed = max(now - self._last_net_time, 0.001)

        bytes_sent_delta = max(curr_net.bytes_sent - self._last_net_io.bytes_sent, 0)
        bytes_recv_delta = max(curr_net.bytes_recv - self._last_net_io.bytes_recv, 0)

        upload_speed_bps = bytes_sent_delta / elapsed
        download_speed_bps = bytes_recv_delta / elapsed

        self._last_net_io = curr_net
        self._last_net_time = now

        # Per-interface information
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
        interfaces = []

        for name, addr_list in addrs.items():
            ipv4 = None
            ipv6 = None
            mac = None
            for addr in addr_list:
                if addr.family == socket.AF_INET:
                    ipv4 = addr.address
                elif hasattr(socket, "AF_INET6") and addr.family == socket.AF_INET6:
                    ipv6 = addr.address
                elif hasattr(psutil, "AF_LINK") and addr.family == psutil.AF_LINK:
                    mac = addr.address

            stat = stats.get(name)
            is_up = stat.isup if stat else False
            speed = stat.speed if stat else 0

            interfaces.append({
                "name": name,
                "is_up": is_up,
                "status": "UP" if is_up else "DOWN",
                "speed_mbps": speed,
                "ipv4": ipv4 or "N/A",
                "ipv6": ipv6 or "N/A",
                "mac": mac or "N/A"
            })

        return {
            "bytes_sent_total": curr_net.bytes_sent,
            "bytes_recv_total": curr_net.bytes_recv,
            "bytes_sent_human": bytes_to_human(curr_net.bytes_sent),
            "bytes_recv_human": bytes_to_human(curr_net.bytes_recv),
            "upload_speed_bps": round(upload_speed_bps, 2),
            "download_speed_bps": round(download_speed_bps, 2),
            "upload_speed_human": f"{bytes_to_human(int(upload_speed_bps))}/s",
            "download_speed_human": f"{bytes_to_human(int(download_speed_bps))}/s",
            "packets_sent": curr_net.packets_sent,
            "packets_recv": curr_net.packets_recv,
            "errin": curr_net.errin,
            "errout": curr_net.errout,
            "dropin": curr_net.dropin,
            "dropout": curr_net.dropout,
            "interfaces": interfaces
        }

    def collect_snapshot(self) -> Dict[str, Any]:
        """Aggregate full system health snapshot at the current moment."""
        timestamp = datetime.now().isoformat()
        snapshot = {
            "timestamp": timestamp,
            "system": self.get_system_info(),
            "cpu": self.get_cpu_metrics(),
            "memory": self.get_memory_metrics(),
            "disk": self.get_disk_metrics(),
            "network": self.get_network_metrics()
        }
        return snapshot

    def record_snapshot(self) -> Dict[str, Any]:
        """Collect and persist metrics snapshot to JSON Lines log."""
        snapshot = self.collect_snapshot()
        try:
            with open(self.metrics_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(snapshot) + "\n")
        except Exception as e:
            logger.error(f"Failed to record snapshot to {self.metrics_log_path}: {e}")
        return snapshot

    def get_history(self, limit: int = 60) -> List[Dict[str, Any]]:
        """Retrieve recent historical metric snapshots from disk."""
        if not os.path.exists(self.metrics_log_path):
            return []
        records = []
        try:
            with open(self.metrics_log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            return records[-limit:]
        except Exception as e:
            logger.error(f"Failed to read history from {self.metrics_log_path}: {e}")
            return []

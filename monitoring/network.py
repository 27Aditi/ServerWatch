"""
ServerWatch - Network Monitoring Module
Collects network interface telemetry, active socket connections,
throughput rates, and listening services.
"""

import socket
import logging
from typing import Dict, Any, List
import psutil

logger = logging.getLogger("serverwatch.network")


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


class NetworkMonitor:
    """Monitors system network interfaces, sockets, and listening ports."""

    def get_interface_details(self) -> List[Dict[str, Any]]:
        """Collect configuration and real-time counters per network interface."""
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
        io_counters = psutil.net_io_counters(pernic=True)

        interfaces = []
        for iface_name, addr_list in addrs.items():
            ipv4 = "N/A"
            netmask = "N/A"
            mac = "N/A"

            for addr in addr_list:
                if addr.family == socket.AF_INET:
                    ipv4 = addr.address
                    netmask = addr.netmask or "N/A"
                elif hasattr(psutil, "AF_LINK") and addr.family == psutil.AF_LINK:
                    mac = addr.address

            stat = stats.get(iface_name)
            is_up = stat.isup if stat else False
            speed = stat.speed if stat else 0
            mtu = stat.mtu if stat else 1500

            io = io_counters.get(iface_name)
            bytes_sent = io.bytes_sent if io else 0
            bytes_recv = io.bytes_recv if io else 0
            errin = io.errin if io else 0
            errout = io.errout if io else 0
            dropin = io.dropin if io else 0
            dropout = io.dropout if io else 0

            interfaces.append({
                "interface": iface_name,
                "status": "UP" if is_up else "DOWN",
                "ipv4": ipv4,
                "netmask": netmask,
                "mac": mac,
                "speed_mbps": speed,
                "mtu": mtu,
                "bytes_sent": bytes_sent,
                "bytes_recv": bytes_recv,
                "bytes_sent_human": bytes_to_human(bytes_sent),
                "bytes_recv_human": bytes_to_human(bytes_recv),
                "errin": errin,
                "errout": errout,
                "dropin": dropin,
                "dropout": dropout
            })

        return interfaces

    def get_connection_summary(self) -> Dict[str, int]:
        """Summarize active TCP socket connection states."""
        summary = {
            "ESTABLISHED": 0,
            "LISTEN": 0,
            "TIME_WAIT": 0,
            "CLOSE_WAIT": 0,
            "SYN_SENT": 0,
            "OTHER": 0,
            "TOTAL": 0
        }
        try:
            connections = psutil.net_connections(kind="inet")
            for conn in connections:
                summary["TOTAL"] += 1
                status = conn.status
                if status in summary:
                    summary[status] += 1
                else:
                    summary["OTHER"] += 1
        except (psutil.AccessDenied, PermissionError):
            logger.debug("Permission denied reading global net_connections (requires root/admin).")
        return summary

    def get_listening_services(self, limit: int = 25) -> List[Dict[str, Any]]:
        """List active TCP/UDP listening ports and responsible processes."""
        listeners = []
        try:
            connections = psutil.net_connections(kind="inet")
            for conn in connections:
                if conn.status == psutil.CONN_LISTEN and conn.laddr:
                    ip = conn.laddr.ip
                    port = conn.laddr.port
                    pid = conn.pid or 0
                    pname = "unknown"
                    if pid:
                        try:
                            pname = psutil.Process(pid).name()
                        except Exception:
                            pname = "unknown"

                    listeners.append({
                        "protocol": "TCP",
                        "local_address": f"{ip}:{port}",
                        "port": port,
                        "pid": pid,
                        "process_name": pname
                    })
        except (psutil.AccessDenied, PermissionError):
            logger.debug("Access denied reading net_connections.")
        return listeners[:limit]

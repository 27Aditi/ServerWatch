"""
ServerWatch - Linux Server Health Monitoring & Automated Maintenance System
Streamlit Infrastructure Dashboard optimized for Streamlit Community Cloud
and Dedicated Linux Servers.
"""

import os
import sys
import json
import time
import tarfile
import subprocess
from datetime import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from monitoring.metrics import SystemMetricsCollector, bytes_to_human, load_config
from monitoring.alerts import AlertEngine, AlertSeverity, AlertStatus
from monitoring.processes import ProcessManager
from monitoring.network import NetworkMonitor
from incident_management.incident_manager import (
    IncidentManager, IncidentSeverity, IncidentStatus, IncidentCategory
)
from incident_management.report_generator import ReportGenerator

# Page Configuration
st.set_page_config(
    page_title="ServerWatch - Linux Server Health Monitor",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Dark Theme CSS
CUSTOM_CSS = """
<style>
    /* Global Styles */
    .stApp {
        background-color: #0d1117;
        color: #c9d1d9;
    }
    
    /* Metric Cards */
    .metric-card {
        background: linear-gradient(135deg, #161b22 0%, #1f242c 100%);
        border: 1px solid #30363d;
        border-radius: 10px;
        padding: 18px 22px;
        margin-bottom: 14px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
    }
    .metric-title {
        font-size: 0.82rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #8b949e;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 2.1rem;
        font-weight: 700;
        line-height: 1.1;
        margin-bottom: 6px;
    }
    .metric-sub {
        font-size: 0.8rem;
        color: #8b949e;
    }
    
    /* Value Color Accents */
    .val-normal { color: #58a6ff; }
    .val-healthy { color: #3fb950; }
    .val-warning { color: #d29922; }
    .val-critical { color: #f85149; }

    /* Status Badges */
    .badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.05em;
    }
    .badge-healthy {
        background-color: rgba(63, 185, 80, 0.15);
        color: #3fb950;
        border: 1px solid rgba(63, 185, 80, 0.4);
    }
    .badge-warning {
        background-color: rgba(210, 153, 34, 0.15);
        color: #d29922;
        border: 1px solid rgba(210, 153, 34, 0.4);
    }
    .badge-critical {
        background-color: rgba(248, 81, 73, 0.15);
        color: #f85149;
        border: 1px solid rgba(248, 81, 73, 0.4);
    }
    .badge-cloud {
        background-color: rgba(88, 166, 255, 0.15);
        color: #58a6ff;
        border: 1px solid rgba(88, 166, 255, 0.4);
    }
    .badge-host {
        background-color: rgba(187, 128, 179, 0.15);
        color: #d2a8ff;
        border: 1px solid rgba(187, 128, 179, 0.4);
    }

    /* Section Banner */
    .section-header {
        font-size: 1.35rem;
        font-weight: 700;
        color: #f0f6fc;
        margin-top: 10px;
        margin-bottom: 18px;
        padding-bottom: 8px;
        border-bottom: 1px solid #21262d;
    }
    
    .notice-box {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-left: 4px solid #58a6ff;
        border-radius: 6px;
        padding: 12px 16px;
        margin-bottom: 16px;
        font-size: 0.88rem;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def detect_runtime_environment():
    """
    Detect whether the application is running inside Streamlit Community Cloud,
    an unprivileged container, or a native dedicated Linux host.
    """
    is_cloud = bool(
        os.environ.get("STREAMLIT_SERVER_BASE_URL_PATH")
        or os.environ.get("IS_STREAMLIT_CLOUD")
        or os.environ.get("STREAMLIT_SHARING_MODE")
        or os.path.exists("/mount")
        or os.path.exists("/app")
        or os.path.exists("/.dockerenv")
    )
    has_systemd = False
    if os.name != "nt" and os.path.exists("/run/systemd/system"):
        try:
            r = subprocess.run(["systemctl", "is-system-running"], capture_output=True, text=True, timeout=1)
            has_systemd = r.returncode in (0, 1)
        except Exception:
            has_systemd = False

    return {
        "is_cloud": is_cloud,
        "has_systemd": has_systemd,
        "is_windows": os.name == "nt",
        "env_title": "Streamlit Community Cloud (Container Sandbox)" if is_cloud else (
            "Dedicated Linux Server (Native systemd)" if has_systemd else "Local / Unprivileged Host"
        )
    }


runtime_env = detect_runtime_environment()


@st.cache_resource
def get_services():
    """Initialize singleton backend services."""
    return {
        "metrics": SystemMetricsCollector(),
        "alerts": AlertEngine(),
        "processes": ProcessManager(),
        "network": NetworkMonitor(),
        "incidents": IncidentManager(),
        "reports": ReportGenerator()
    }


services = get_services()
collector = services["metrics"]
alert_engine = services["alerts"]
process_mgr = services["processes"]
net_mon = services["network"]
incident_mgr = services["incidents"]
report_gen = services["reports"]

# Record current telemetry cycle on load
current_snapshot = collector.record_snapshot()
active_alerts = alert_engine.evaluate(current_snapshot)

# Auto-generate incidents for critical alerts if any
for alt in active_alerts:
    if alt.get("severity") in [AlertSeverity.CRITICAL, AlertSeverity.HIGH]:
        cat = IncidentCategory.RESOURCE_EXHAUSTION
        if "Disk" in alt.get("resource", ""):
            cat = IncidentCategory.DISK_PRESSURE
        elif "Load" in alt.get("resource", ""):
            cat = IncidentCategory.HIGH_LOAD
        incident_mgr.create_incident(
            category=cat,
            severity=alt.get("severity"),
            description=alt.get("message"),
            affected_resource=alt.get("resource")
        )

# Fetch current state
sys_info = current_snapshot["system"]
cpu = current_snapshot["cpu"]
mem = current_snapshot["memory"]
disk = current_snapshot["disk"]
net = current_snapshot["network"]
all_incidents = incident_mgr.get_incidents()
inc_stats = incident_mgr.get_statistics()

# Compute overall health status
overall_health = "HEALTHY"
badge_class = "badge-healthy"
if inc_stats["critical"] > 0 or cpu["utilization_percent"] >= 80 or mem["utilization_percent"] >= 85:
    overall_health = "CRITICAL"
    badge_class = "badge-critical"
elif inc_stats["high"] > 0 or cpu["utilization_percent"] >= 70 or mem["utilization_percent"] >= 75:
    overall_health = "WARNING"
    badge_class = "badge-warning"


# --- SIDEBAR NAVIGATION ---
with st.sidebar:
    st.markdown("### 🖥️ **ServerWatch**")
    st.markdown(f"<span class='badge {badge_class}'>● {overall_health}</span>", unsafe_allow_html=True)
    
    # Runtime badge
    if runtime_env["is_cloud"]:
        st.markdown("<span class='badge badge-cloud'>☁️ Hosted: Streamlit Cloud</span>", unsafe_allow_html=True)
    else:
        st.markdown("<span class='badge badge-host'>🖥️ Host: Local / Dedicated</span>", unsafe_allow_html=True)

    st.caption(f"Host Node: `{sys_info.get('hostname')}` | {sys_info.get('distro')}")
    st.divider()

    nav_selection = st.radio(
        "Navigation Menu",
        [
            "📊 Overview",
            "📈 Resource Monitoring",
            "⚙️ Process Management",
            "🚨 Alerts & Incidents",
            "🛡️ System Services",
            "🛠️ Maintenance & Automation",
            "ℹ️ System Information"
        ],
        index=0
    )

    st.divider()
    st.markdown("#### ⚡ Operational Controls")
    if st.button("🔄 Collect Telemetry Now", use_container_width=True):
        st.rerun()

    auto_refresh = st.checkbox("Auto-refresh (10s)", value=False)
    if auto_refresh:
        time.sleep(10)
        st.rerun()

    st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")


# ==============================================================================
# 1. OVERVIEW PAGE
# ==============================================================================
if nav_selection == "📊 Overview":
    st.markdown("<div class='section-header'>📊 Server Infrastructure Overview</div>", unsafe_allow_html=True)

    # Transparency Notice for Hosted Streamlit Cloud
    if runtime_env["is_cloud"]:
        st.markdown("""
        <div class='notice-box'>
            <strong>☁️ Streamlit Community Cloud Hosted Runtime:</strong><br>
            The telemetry presented below is <strong>real-time hardware metrics from the live Streamlit Cloud container sandbox</strong> 
            (Container CPU, RAM allocation, filesystem, and active Python processes).<br>
            <em>Note: Streamlit Community Cloud operates within an isolated sandbox and does not monitor external remote servers. Privileged operations (systemd daemons, crontab edits, process killing) are disabled for hosted security.</em>
        </div>
        """, unsafe_allow_html=True)

    # Health Banner
    if overall_health == "HEALTHY":
        st.success(f"✅ **System Status Healthy** — All monitored parameters (CPU, Memory, Disk) are operating within safe bounds.")
    elif overall_health == "WARNING":
        st.warning(f"⚠️ **System Warning** — One or more resources are nearing capacity limits. Review active alerts below.")
    else:
        st.error(f"🚨 **System Status Critical** — Threshold breaches or critical incidents detected! Immediate operator review required.")

    # 4 Primary Metric Cards
    c1, c2, c3, c4 = st.columns(4)

    # CPU Card
    cpu_val = cpu["utilization_percent"]
    cpu_col = "val-critical" if cpu_val >= 80 else ("val-warning" if cpu_val >= 70 else "val-normal")
    with c1:
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-title'>CPU Utilization</div>
            <div class='metric-value {cpu_col}'>{cpu_val}%</div>
            <div class='metric-sub'>Cores: {cpu['logical_cores']} | Load: {cpu['load_1m']} (1m)</div>
        </div>
        """, unsafe_allow_html=True)

    # RAM Card
    mem_val = mem["utilization_percent"]
    mem_col = "val-critical" if mem_val >= 85 else ("val-warning" if mem_val >= 75 else "val-normal")
    with c2:
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-title'>Memory Usage</div>
            <div class='metric-value {mem_col}'>{mem_val}%</div>
            <div class='metric-sub'>{mem['available_human']} free of {mem['total_human']}</div>
        </div>
        """, unsafe_allow_html=True)

    # Disk Card
    disk_val = disk["max_utilization_percent"]
    disk_col = "val-critical" if disk_val >= 85 else ("val-warning" if disk_val >= 75 else "val-normal")
    with c3:
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-title'>Primary Storage</div>
            <div class='metric-value {disk_col}'>{disk_val}%</div>
            <div class='metric-sub'>Partitions monitored: {len(disk['partitions'])}</div>
        </div>
        """, unsafe_allow_html=True)

    # Uptime Card
    with c4:
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-title'>System Uptime</div>
            <div class='metric-value val-healthy' style='font-size: 1.6rem;'>{sys_info['uptime_human']}</div>
            <div class='metric-sub'>Booted: {sys_info['boot_time']}</div>
        </div>
        """, unsafe_allow_html=True)

    # Secondary Quick Stat Bar
    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Active Alerts", len(alert_engine.get_active_alerts()))
    q2.metric("Open Incidents", inc_stats["active"] + inc_stats["investigating"])
    q3.metric("Network Upload Speed", net["upload_speed_human"])
    q4.metric("Network Download Speed", net["download_speed_human"])

    st.markdown("<br>", unsafe_allow_html=True)

    # Recent Trends (CPU and Memory historical chart)
    history = collector.get_history(limit=30)
    if history:
        df_hist = []
        for h in history:
            ts = h.get("timestamp", "")
            time_label = ts[11:19] if len(ts) >= 19 else ts
            df_hist.append({
                "Time": time_label,
                "CPU (%)": h.get("cpu", {}).get("utilization_percent", 0.0),
                "RAM (%)": h.get("memory", {}).get("utilization_percent", 0.0)
            })
        df_plot = pd.DataFrame(df_hist)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_plot["Time"], y=df_plot["CPU (%)"],
            mode="lines+markers", name="CPU Utilization (%)",
            line=dict(color="#58a6ff", width=2.5)
        ))
        fig.add_trace(go.Scatter(
            x=df_plot["Time"], y=df_plot["RAM (%)"],
            mode="lines+markers", name="RAM Utilization (%)",
            line=dict(color="#3fb950", width=2.5)
        ))
        fig.add_hline(y=80, line_dash="dash", line_color="#f85149", annotation_text="CPU Critical (80%)")
        fig.add_hline(y=85, line_dash="dot", line_color="#d29922", annotation_text="RAM Critical (85%)")

        fig.update_layout(
            title="Real-Time System Telemetry (Recent Snapshots)",
            template="plotly_dark",
            paper_bgcolor="#161b22",
            plot_bgcolor="#0d1117",
            height=340,
            margin=dict(l=40, r=40, t=50, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)


# ==============================================================================
# 2. RESOURCE MONITORING
# ==============================================================================
elif nav_selection == "📈 Resource Monitoring":
    st.markdown("<div class='section-header'>📈 Detailed Hardware & Network Telemetry</div>", unsafe_allow_html=True)

    tab_cpu, tab_mem, tab_disk, tab_net = st.tabs(["CPU & Load", "Memory & Swap", "Disk Storage", "Network Traffic"])

    # TAB 1: CPU
    with tab_cpu:
        c1, c2 = st.columns([2, 1])
        with c1:
            per_core = cpu.get("per_core_percent", [])
            core_df = pd.DataFrame({
                "Core": [f"Core {i}" for i in range(len(per_core))],
                "Usage (%)": per_core
            })
            fig_cores = px.bar(
                core_df, x="Core", y="Usage (%)",
                title="Per-Core CPU Utilization",
                color="Usage (%)",
                color_continuous_scale=["#3fb950", "#d29922", "#f85149"],
                range_y=[0, 100]
            )
            fig_cores.update_layout(template="plotly_dark", paper_bgcolor="#161b22", plot_bgcolor="#0d1117", height=320)
            st.plotly_chart(fig_cores, use_container_width=True)

        with c2:
            st.markdown("#### System Load Averages")
            st.markdown("The Linux load average represents the average number of processes in runnable or uninterruptible state.")
            st.metric("1-Minute Load Average", f"{cpu['load_1m']}", f"Ratio: {cpu['load_ratio_1m']} / core")
            st.metric("5-Minute Load Average", f"{cpu['load_5m']}")
            st.metric("15-Minute Load Average", f"{cpu['load_15m']}")
            st.caption(f"Logical Cores: {cpu['logical_cores']} | Frequency: {cpu.get('frequency_mhz', 0)} MHz")

    # TAB 2: MEMORY
    with tab_mem:
        col_m1, col_m2 = st.columns([1, 1])
        with col_m1:
            mem_breakdown = pd.DataFrame({
                "State": ["Used", "Free", "Cached / Available"],
                "Bytes": [mem["used_bytes"], mem["free_bytes"], max(mem["available_bytes"] - mem["free_bytes"], 0)]
            })
            fig_mem_pie = px.pie(
                mem_breakdown, values="Bytes", names="State",
                title=f"RAM Allocation Breakdown (Total: {mem['total_human']})",
                color_discrete_sequence=["#f85149", "#3fb950", "#58a6ff"],
                hole=0.45
            )
            fig_mem_pie.update_layout(template="plotly_dark", paper_bgcolor="#161b22", height=320)
            st.plotly_chart(fig_mem_pie, use_container_width=True)

        with col_m2:
            st.markdown("#### Memory & Swap Details")
            st.write(f"- **Total Virtual Memory:** `{mem['total_human']}`")
            st.write(f"- **Used Memory:** `{mem['used_human']}` ({mem['utilization_percent']}%)")
            st.write(f"- **Available Memory:** `{mem['available_human']}`")
            st.write(f"- **Cached Memory:** `{mem['cached_human']}`")
            st.write(f"- **Kernel Buffers:** `{mem['buffers_human']}`")
            st.divider()
            st.write(f"- **Total Swap Space:** `{mem['swap_total_human']}`")
            st.write(f"- **Used Swap:** `{mem['swap_used_human']}` ({mem['swap_percent']}%)")

    # TAB 3: DISK
    with tab_disk:
        st.markdown("#### Filesystem Partitions")
        partitions = disk.get("partitions", [])
        if partitions:
            p_df = pd.DataFrame(partitions)
            p_display = p_df[["mountpoint", "device", "fstype", "utilization_percent", "used_human", "free_human", "total_human"]]
            p_display.columns = ["Mountpoint", "Device", "FS Type", "Used (%)", "Used", "Free", "Total"]
            st.dataframe(p_display, use_container_width=True)

            fig_disk = px.bar(
                p_df, x="mountpoint", y="utilization_percent",
                color="utilization_percent",
                title="Disk Mountpoint Utilization (%)",
                color_continuous_scale=["#3fb950", "#d29922", "#f85149"],
                range_y=[0, 100]
            )
            fig_disk.add_hline(y=85, line_dash="dash", line_color="#f85149", annotation_text="Critical (85%)")
            fig_disk.update_layout(template="plotly_dark", paper_bgcolor="#161b22", plot_bgcolor="#0d1117", height=280)
            st.plotly_chart(fig_disk, use_container_width=True)

        # Disk I/O
        io = disk.get("io", {})
        st.markdown("#### Disk I/O Throughput")
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Total Read", io.get("read_human", "0 B"))
        d2.metric("Total Written", io.get("write_human", "0 B"))
        d3.metric("Read Operations", f"{io.get('read_count', 0):,}")
        d4.metric("Write Operations", f"{io.get('write_count', 0):,}")

    # TAB 4: NETWORK
    with tab_net:
        st.markdown("#### Network Interfaces & Transfer Speeds")
        n1, n2, n3, n4 = st.columns(4)
        n1.metric("Upload Speed", net.get("upload_speed_human", "0 B/s"))
        n2.metric("Download Speed", net.get("download_speed_human", "0 B/s"))
        n3.metric("Cumulative Sent", net.get("bytes_sent_human", "0 B"))
        n4.metric("Cumulative Received", net.get("bytes_recv_human", "0 B"))

        st.markdown("##### Configured Network Interfaces")
        if net.get("interfaces"):
            iface_df = pd.DataFrame(net["interfaces"])
            st.dataframe(iface_df[["name", "status", "ipv4", "speed_mbps", "mac"]], use_container_width=True)


# ==============================================================================
# 3. PROCESS MANAGEMENT
# ==============================================================================
elif nav_selection == "⚙️ Process Management":
    st.markdown("<div class='section-header'>⚙️ Linux Process Monitoring & Safe Management</div>", unsafe_allow_html=True)

    summary = process_mgr.get_process_summary()
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("Total Processes", summary["total"])
    s2.metric("Running", summary["running"])
    s3.metric("Sleeping", summary["sleeping"])
    s4.metric("Stopped", summary["stopped"])
    s5.metric("Zombie", summary["zombie"], delta="Defunct" if summary["zombie"] > 0 else "None", delta_color="inverse")

    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("##### ⚡ Top 10 CPU Consuming Processes")
        top_cpu = process_mgr.get_top_cpu_processes(limit=10)
        df_top_cpu = pd.DataFrame(top_cpu)[["pid", "name", "username", "cpu_percent", "memory_percent", "threads"]]
        df_top_cpu.columns = ["PID", "Process Name", "User", "CPU %", "RAM %", "Threads"]
        st.dataframe(df_top_cpu, use_container_width=True, hide_index=True)

    with c2:
        st.markdown("##### 💾 Top 10 Memory Consuming Processes")
        top_mem = process_mgr.get_top_memory_processes(limit=10)
        df_top_mem = pd.DataFrame(top_mem)[["pid", "name", "username", "memory_percent", "memory_rss_human", "cpu_percent"]]
        df_top_mem.columns = ["PID", "Process Name", "User", "RAM %", "RSS Mem", "CPU %"]
        st.dataframe(df_top_mem, use_container_width=True, hide_index=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("##### 🔍 Full Process Table")

    search_query = st.text_input("Filter processes by name or user:", value="")
    all_procs = process_mgr.get_all_processes(limit=200)
    if search_query:
        all_procs = [p for p in all_procs if search_query.lower() in p["name"].lower() or search_query.lower() in p["username"].lower()]

    df_all = pd.DataFrame(all_procs)[["pid", "name", "username", "status", "cpu_percent", "memory_percent", "memory_rss_human", "create_time"]]
    df_all.columns = ["PID", "Name", "User", "Status", "CPU %", "RAM %", "Memory RSS", "Started At"]
    st.dataframe(df_all, use_container_width=True, hide_index=True)

    # PROCESS TERMINATION SECTION
    with st.expander("🛡️ Process Inspection & Controlled Termination", expanded=False):
        if runtime_env["is_cloud"]:
            st.info(
                "🔒 **Process Termination Disabled in Streamlit Community Cloud**\n\n"
                "In hosted cloud environments, arbitrary signal dispatch (`SIGTERM`/`SIGKILL`) is disabled "
                "to preserve container stability and prevent terminating the active web server. "
                "This action is fully functional when running on a dedicated Linux host with administrative privileges."
            )
            col_p1, col_p2 = st.columns([1, 2])
            with col_p1:
                target_pid = st.number_input("Target Process PID:", min_value=1, value=1, step=1)
                inspect_btn = st.button("Inspect Process Details")
            if inspect_btn:
                proc_details = process_mgr.get_process_by_pid(target_pid)
                if proc_details:
                    st.json(proc_details)
                else:
                    st.error(f"PID {target_pid} not found or permission denied.")
        else:
            st.markdown(
                "> **Safety Policy:** In accordance with Linux Infrastructure Engineering standards, ServerWatch **never** "
                "kills processes automatically. Any termination requires manual review, reason logging, and explicit confirmation."
            )
            col_p1, col_p2, col_p3 = st.columns([1, 2, 1])
            with col_p1:
                target_pid = st.number_input("Target Process PID:", min_value=2, value=100, step=1)
                inspect_btn = st.button("Inspect Process Details")

            if inspect_btn:
                proc_details = process_mgr.get_process_by_pid(target_pid)
                if proc_details:
                    st.json(proc_details)
                else:
                    st.error(f"PID {target_pid} not found or access denied.")

            with col_p2:
                kill_reason = st.text_input("Operational reason for termination:", placeholder="e.g., Unresponsive daemon / runaway memory")
                confirm_kill = st.checkbox("I confirm that I want to terminate this process (SIGTERM -> SIGKILL).")

            with col_p3:
                st.write("")
                st.write("")
                if st.button("🚨 Terminate Process", type="primary"):
                    result = process_mgr.terminate_process_safely(
                        pid=target_pid,
                        user_confirmed=confirm_kill,
                        reason=kill_reason
                    )
                    if result["success"]:
                        st.success(result["message"])
                    else:
                        st.error(result["message"])


# ==============================================================================
# 4. ALERTS & INCIDENTS
# ==============================================================================
elif nav_selection == "🚨 Alerts & Incidents":
    st.markdown("<div class='section-header'>🚨 Alert Stream & Enterprise Incident Management</div>", unsafe_allow_html=True)

    # Summary Row
    i1, i2, i3, i4, i5 = st.columns(5)
    i1.metric("Total Incidents", inc_stats["total"])
    i2.metric("Active", inc_stats["active"])
    i3.metric("Investigating", inc_stats["investigating"])
    i4.metric("Resolved", inc_stats["resolved"])
    i5.metric("Critical Breaches", inc_stats["critical"])

    # Active Real-Time Alerts
    st.markdown("##### ⚡ Active Threshold Alerts")
    active_alts = alert_engine.get_active_alerts()
    if active_alts:
        for alt in active_alts:
            sev_class = "badge-critical" if alt["severity"] == "CRITICAL" else "badge-warning"
            st.markdown(
                f"<div style='background-color: #161b22; border-left: 4px solid {'#f85149' if alt['severity'] == 'CRITICAL' else '#d29922'}; padding: 12px 16px; margin-bottom: 8px; border-radius: 4px;'>"
                f"<span class='badge {sev_class}'>{alt['severity']}</span> "
                f"<strong>[{alt['resource']}]</strong> {alt['message']} "
                f"<span style='float: right; color: #8b949e; font-size: 0.8rem;'>{alt['timestamp']}</span>"
                f"</div>",
                unsafe_allow_html=True
            )
    else:
        st.info("No active threshold alerts. Hardware metrics within normal limits.")

    st.markdown("<br>", unsafe_allow_html=True)

    # Severity Distribution Chart & Incident Workflow
    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown("##### Incident Severity Breakdown")
        sev_counts = {
            "CRITICAL": inc_stats["critical"],
            "HIGH": inc_stats["high"],
            "MEDIUM": inc_stats["medium"],
            "LOW": inc_stats["low"]
        }
        df_sev = pd.DataFrame([{"Severity": k, "Count": v} for k, v in sev_counts.items() if v > 0])
        if not df_sev.empty:
            fig_sev = px.pie(
                df_sev, values="Count", names="Severity",
                color="Severity",
                color_discrete_map={"CRITICAL": "#f85149", "HIGH": "#d29922", "MEDIUM": "#58a6ff", "LOW": "#8b949e"},
                hole=0.45
            )
            fig_sev.update_layout(template="plotly_dark", paper_bgcolor="#161b22", height=260, margin=dict(t=20, b=20, l=20, r=20))
            st.plotly_chart(fig_sev, use_container_width=True)
        else:
            st.caption("No historical incident data recorded yet.")

    with c2:
        st.markdown("##### Incident Lifecycle & Resolution Workflow")
        open_incs = [i for i in all_incidents if i.get("status") in [IncidentStatus.ACTIVE, IncidentStatus.INVESTIGATING]]
        if open_incs:
            target_inc_id = st.selectbox(
                "Select Incident to Update:",
                options=[i["incident_id"] for i in open_incs],
                format_func=lambda x: f"{x} - {next((i['description'] for i in open_incs if i['incident_id'] == x), '')[:60]}"
            )
            new_st = st.selectbox("Update Status:", [IncidentStatus.INVESTIGATING, IncidentStatus.RESOLVED, IncidentStatus.FALSE_POSITIVE])
            notes = st.text_area("Resolution Notes / RCA:", placeholder="Describe the remediation actions taken or investigation findings...")
            if st.button("Update Incident Status", type="primary"):
                updated = incident_mgr.update_incident_status(target_inc_id, new_st, notes)
                if updated:
                    st.success(f"Incident {target_inc_id} updated to {new_st}!")
                    st.rerun()
        else:
            st.success("All recorded incidents have been resolved!")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("##### 📋 Master Incident Log")

    # Filters
    f1, f2, f3 = st.columns([1, 1, 2])
    with f1:
        f_sev = st.selectbox("Filter by Severity:", ["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"])
    with f2:
        f_stat = st.selectbox("Filter by Status:", ["ALL", "ACTIVE", "INVESTIGATING", "RESOLVED", "FALSE_POSITIVE"])

    filtered_incs = incident_mgr.get_incidents(severity=f_sev, status=f_stat)
    if filtered_incs:
        df_incs = pd.DataFrame(filtered_incs)[["incident_id", "timestamp", "category", "severity", "affected_resource", "description", "status", "resolution"]]
        df_incs.columns = ["Incident ID", "Timestamp", "Category", "Severity", "Resource", "Description", "Status", "Resolution"]
        st.dataframe(df_incs, use_container_width=True, hide_index=True)
    else:
        st.write("No incidents match the selected filter criteria.")

    # Export Buttons
    st.markdown("##### 📤 Export Incident Audit Reports")
    col_e1, col_e2 = st.columns(2)
    with col_e1:
        csv_file = report_gen.export_incidents_csv()
        with open(csv_file, "r", encoding="utf-8") as f:
            st.download_button(
                label="📥 Download Incidents as CSV",
                data=f.read(),
                file_name=os.path.basename(csv_file),
                mime="text/csv",
                use_container_width=True
            )
    with col_e2:
        rep_result = report_gen.generate_health_report()
        with open(rep_result["markdown_path"], "r", encoding="utf-8") as f:
            st.download_button(
                label="📥 Download Executive Health Report (Markdown)",
                data=f.read(),
                file_name=os.path.basename(rep_result["markdown_path"]),
                mime="text/markdown",
                use_container_width=True
            )


# ==============================================================================
# 5. SYSTEM SERVICES
# ==============================================================================
elif nav_selection == "🛡️ System Services":
    st.markdown("<div class='section-header'>🛡️ Core Linux Services & Daemon Inspection</div>", unsafe_allow_html=True)

    config_data = load_config()
    monitored_services = config_data.get("services_to_monitor", ["ssh", "cron", "nginx", "docker", "systemd-journald", "ufw", "rsyslog"])

    if not runtime_env["has_systemd"]:
        st.warning(
            "⚠️ **Linux Service Inspection (systemd) Unavailable in Container Environment**\n\n"
            "This application is running inside a lightweight container sandbox (Streamlit Community Cloud). "
            "Containers do not run the **systemd init system** (PID 1 is the container process, not `systemd`), "
            "meaning `systemctl` commands cannot query daemon statuses.\n\n"
            "**Real-world usage:** To monitor `systemd` units (`ssh`, `nginx`, `docker`, etc.), run ServerWatch on a dedicated Ubuntu/Debian Linux virtual machine or bare-metal host."
        )

        service_results = []
        for svc in monitored_services:
            service_results.append({
                "Service Name": svc,
                "Operational Status": "UNAVAILABLE (Container Sandbox)",
                "Supervision Requirement": "Requires systemd host daemon"
            })
        st.dataframe(pd.DataFrame(service_results), use_container_width=True, hide_index=True)

        st.markdown("#### Shell Service Audit Script (`scripts/service_monitor.sh`)")
        st.markdown("When deployed on a live Ubuntu Linux host, the following script audits the services via `systemctl`:")
        with open("scripts/service_monitor.sh", "r", encoding="utf-8") as f:
            st.code(f.read(), language="bash")
    else:
        # Native Linux host with systemd present
        service_results = []
        for svc in monitored_services:
            try:
                res = subprocess.run(["systemctl", "is-active", svc], capture_output=True, text=True, timeout=2)
                state = res.stdout.strip()
                status = "RUNNING" if state == "active" else ("FAILED" if state == "failed" else "INACTIVE")
            except Exception:
                status = "UNKNOWN"

            service_results.append({
                "Service Name": svc,
                "Operational Status": status,
                "Description": f"Core daemon ({svc})"
            })
        st.dataframe(pd.DataFrame(service_results), use_container_width=True, hide_index=True)


# ==============================================================================
# 6. MAINTENANCE & AUTOMATION
# ==============================================================================
elif nav_selection == "🛠️ Maintenance & Automation":
    st.markdown("<div class='section-header'>🛠️ Automated Maintenance & Scheduling Center</div>", unsafe_allow_html=True)

    tab_clean, tab_cron, tab_backup = st.tabs(["🧹 Safe Log Cleanup", "⏰ Cron Automation", "📦 Log Archival Backup"])

    # TAB 1: CLEANUP
    with tab_clean:
        st.markdown("#### Safe Application Log Cleanup")
        st.markdown(
            "> By default, cleanup runs in **Dry-Run mode** to audit files without touching them. "
            "Deletion is permanently blocked unless the operator explicitly activates live confirmation."
        )

        col_c1, col_c2 = st.columns([1, 2])
        with col_c1:
            retention_days = st.slider("Retention Threshold (Days):", min_value=1, max_value=60, value=7)
            target_folder = st.selectbox("Target Directory:", ["logs", "backups", "reports"])
            confirm_live = st.checkbox("Enable Live Deletion (Permanent)", value=False)

        with col_c2:
            st.write("")
            st.write("")
            if st.button("Execute Cleanup Routine", type="primary" if confirm_live else "secondary"):
                # Safe pure Python file evaluation
                target_path = target_folder
                if os.path.exists(target_path):
                    now_ts = time.time()
                    candidates = []
                    for fname in os.listdir(target_path):
                        fpath = os.path.join(target_path, fname)
                        if os.path.isfile(fpath) and not fname.startswith("."):
                            age_days = (now_ts - os.path.getmtime(fpath)) / 86400.0
                            if age_days >= retention_days:
                                candidates.append((fpath, fname, os.path.getsize(fpath), age_days))

                    if not candidates:
                        st.info(f"No files older than {retention_days} days found in '{target_folder}'.")
                    else:
                        st.write(f"Found **{len(candidates)}** candidate files:")
                        for p, fn, sz, age in candidates:
                            st.write(f"- `{fn}` ({bytes_to_human(sz)}, age: {age:.1f} days)")

                        if confirm_live:
                            deleted = 0
                            for p, fn, sz, age in candidates:
                                try:
                                    os.unlink(p)
                                    deleted += 1
                                except Exception as e:
                                    st.error(f"Failed to delete {fn}: {e}")
                            st.success(f"Confirmed cleanup: {deleted} files safely deleted.")
                        else:
                            st.warning("DRY-RUN completed. No files were modified. Check 'Enable Live Deletion' to proceed.")
                else:
                    st.info(f"Directory '{target_folder}' does not exist.")

    # TAB 2: CRON
    with tab_cron:
        st.markdown("#### Automated Cron Schedule Configuration")
        if runtime_env["is_cloud"]:
            st.info(
                "ℹ️ **Cron Service Status:** Ephemeral web containers (such as Streamlit Community Cloud) "
                "do not host a persistent background `cron` daemon. The schedule definitions below are designed "
                "to be installed on your dedicated Linux server using `automation/cron_setup.sh`."
            )

        cron_jobs_table = pd.DataFrame([
            {"Task": "System Telemetry Check", "Frequency": "Every 5 mins (`*/5 * * * *`)", "Script / Command": "python -m automation.scheduler --once"},
            {"Task": "Disk Space Monitoring", "Frequency": "Hourly (`0 * * * *`)", "Script / Command": "bash scripts/disk_monitor.sh 85"},
            {"Task": "Linux Service Health Audit", "Frequency": "Every 30 mins (`*/30 * * * *`)", "Script / Command": "bash scripts/service_monitor.sh"},
            {"Task": "Daily Health Report Generation", "Frequency": "Daily at 00:00 (`0 0 * * *`)", "Script / Command": "python -m automation.scheduler --report"},
            {"Task": "Weekly Log Archival Backup", "Frequency": "Weekly Sunday 02:00 (`0 2 * * 0`)", "Script / Command": "bash scripts/backup_logs.sh logs backups"},
            {"Task": "Weekly Log Prune (Dry-run)", "Frequency": "Weekly Sunday 03:00 (`0 3 * * 0`)", "Script / Command": "bash scripts/log_cleanup.sh --days 14 --dry-run"}
        ])
        st.dataframe(cron_jobs_table, use_container_width=True, hide_index=True)

        st.markdown("##### Manage Cron Jobs on Linux Host via CLI")
        st.code("""# Install ServerWatch jobs into crontab:
bash automation/cron_setup.sh --install

# View active crontab:
bash automation/cron_setup.sh --show

# Remove only ServerWatch jobs:
bash automation/cron_setup.sh --remove
""", language="bash")

    # TAB 3: BACKUP
    with tab_backup:
        st.markdown("#### Log Archival & Backup")
        st.markdown("Compresses monitoring telemetry and incident logs into a timestamped `.tar.gz` archive.")
        
        # Pure Python safe backup (works in Cloud without root/external tar binary)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = "backups"
        os.makedirs(backup_dir, exist_ok=True)
        archive_name = f"serverwatch_logs_{ts}.tar.gz"
        archive_path = os.path.join(backup_dir, archive_name)

        if st.button("📦 Create Compressed Backup Archive Now", type="primary"):
            with tarfile.open(archive_path, "w:gz") as tar:
                if os.path.exists("logs"):
                    tar.add("logs", arcname="logs")
            st.success(f"Archive created: `{archive_name}` ({bytes_to_human(os.path.getsize(archive_path))})")

            with open(archive_path, "rb") as bf:
                st.download_button(
                    label="📥 Download Backup Tarball",
                    data=bf.read(),
                    file_name=archive_name,
                    mime="application/gzip"
                )


# ==============================================================================
# 7. SYSTEM INFORMATION
# ==============================================================================
elif nav_selection == "ℹ️ System Information":
    st.markdown("<div class='section-header'>ℹ️ Host Specifications & Environment Details</div>", unsafe_allow_html=True)

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("#### Operating System Details")
        st.write(f"- **Runtime Environment:** `{runtime_env['env_title']}`")
        st.write(f"- **Distribution / OS:** `{sys_info.get('distro')}`")
        st.write(f"- **OS Family:** `{sys_info.get('os_name')}`")
        st.write(f"- **Kernel Release:** `{sys_info.get('kernel_release')}`")
        st.write(f"- **Architecture:** `{sys_info.get('architecture')}`")
        st.write(f"- **Hostname:** `{sys_info.get('hostname')}`")
        st.write(f"- **Boot Timestamp:** `{sys_info.get('boot_time')}`")
        st.write(f"- **System Uptime:** `{sys_info.get('uptime_human')}`")

    with c2:
        st.markdown("#### Hardware & Container Telemetry")
        st.write(f"- **Processor:** `{sys_info.get('processor')}`")
        st.write(f"- **Logical CPU Cores:** `{cpu.get('logical_cores')}`")
        st.write(f"- **Physical CPU Cores:** `{cpu.get('physical_cores')}`")
        st.write(f"- **Base Frequency:** `{cpu.get('frequency_mhz')} MHz`")
        st.write(f"- **Total Memory (RAM):** `{mem.get('total_human')}`")
        st.write(f"- **Python Version:** `{sys_info.get('python_version')}`")
        st.write(f"- **Platform Type:** `{'Containerized Cloud' if runtime_env['is_cloud'] else 'Host System'}`")
        st.write(f"- **Application Version:** `ServerWatch v1.0.0 (Cloud & Linux Ready)`")

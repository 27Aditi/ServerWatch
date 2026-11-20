# ServerWatch 🖥️ – Linux Server Health Monitoring & Automated Maintenance System

[![Streamlit Cloud](https://img.shields.io/badge/Streamlit%20Cloud-Deployed-brightgreen.svg)](https://share.streamlit.io/)
[![Python](https://img.shields.io/badge/Python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![OS](https://img.shields.io/badge/OS-Ubuntu%20Linux%20%7C%20Debian%20Container-orange.svg)](https://ubuntu.com/)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)

**ServerWatch** is an infrastructure health monitoring and automated maintenance platform. It combines Linux systems telemetry, threshold alerting, incident management, Bash automation scripts, and an interactive dark-themed dashboard.

---

## ☁️ Deployment on Streamlit Community Cloud

ServerWatch is fully configured to deploy on **Streamlit Community Cloud** with `app.py` as the entrypoint.

### ⚠️ Scope & Operational Transparency in Hosted Cloud Mode
When deployed on Streamlit Community Cloud:
- **Actual Monitored Telemetry:** The dashboard displays real-time hardware metrics (CPU utilization, RAM allocation, disk storage, network transfer rates, and running processes) of the **live Streamlit Cloud Debian container runtime**.
- **External Servers Notice:** Streamlit Community Cloud runs in an isolated container sandbox. It does **not** automatically connect to or monitor remote external Linux machines unless an agent or external API is configured to push telemetry.
- **Privileged Linux Operations:** Ephemeral cloud containers do not run the `systemd` init daemon and enforce unprivileged security boundaries. Consequently:
  - `systemd` service monitoring (`systemctl`) is flagged as unavailable in container mode.
  - Process termination (`SIGTERM`/`SIGKILL`) is disabled in the hosted dashboard to protect container stability.
  - Scheduled `cron` jobs are designed to be installed on a dedicated Linux host via `automation/cron_setup.sh`.

---

### 🚀 Step-by-Step Streamlit Cloud Deployment Guide

1. **Push your code to GitHub:**
   Ensure this repository is pushed to your GitHub account (e.g. `https://github.com/27Aditi/ServerWatch`):
   ```bash
   git add .
   git commit -m "Configure ServerWatch for Streamlit Community Cloud deployment"
   git branch -M main
   git remote add origin https://github.com/27Aditi/ServerWatch.git
   git push -u origin main
   ```

2. **Access Streamlit Community Cloud:**
   - Navigate to [share.streamlit.io](https://share.streamlit.io/) and sign in with your GitHub account.

3. **Deploy the Application:**
   - Click **"Create app"** (or **"New app"**).
   - Fill in the deployment form:
     - **Repository:** `27Aditi/ServerWatch` (or select from dropdown)
     - **Branch:** `main`
     - **Main file path:** `app.py`
     - **App URL:** (Optional custom subdomain, e.g. `serverwatch-monitor.streamlit.app`)
   - Click **"Deploy!"**.

4. **Verification:**
   - Streamlit Cloud automatically reads `requirements.txt`, provisions the Python 3.12/Debian container, and launches the dashboard.
   - The sidebar displays `☁️ Hosted: Streamlit Cloud` indicating container mode.

---

## 🏛️ Project Architecture

```
ServerWatch/
├── app.py                         # Streamlit infrastructure dashboard (Cloud & Host ready)
├── requirements.txt               # Dependencies: psutil, streamlit, plotly, pandas, pytest
├── pytest.ini                     # Pytest configuration
├── run_tests.py                   # Automated test runner (15 unit tests)
├── README.md                      # Documentation & deployment guide
│
├── config/
│   └── settings.json              # Configurable thresholds, file paths, and monitored services
│
├── monitoring/
│   ├── __init__.py
│   ├── metrics.py                 # Telemetry collector (CPU, RAM, Disk, Load, Network)
│   ├── alerts.py                  # Threshold evaluation engine (LOW, MEDIUM, HIGH, CRITICAL)
│   ├── processes.py               # Process inspection and audited safe termination
│   └── network.py                 # Network interface details and transfer throughput
│
├── scripts/
│   ├── system_info.sh             # Linux OS, kernel version, CPU, memory, and uptime
│   ├── disk_monitor.sh            # Filesystem usage & inode inspection with threshold alerting
│   ├── process_monitor.sh         # Top CPU and RAM process inspector using ps
│   ├── log_cleanup.sh             # Safe log cleanup (Safe Dry-Run by default; requires --confirm)
│   ├── service_monitor.sh         # Core Linux daemon state inspection (systemctl)
│   └── backup_logs.sh             # Timestamped tar.gz log archiver with disk space validation
│
├── automation/
│   ├── __init__.py
│   ├── scheduler.py               # Automation engine (Daemon mode, one-shot cron runner)
│   └── cron_setup.sh              # Idempotent crontab installer, inspector, and remover
│
├── incident_management/
│   ├── __init__.py
│   ├── incident_manager.py        # Incident lifecycle (INC-YYYYMMDD-XXXX, deduplication, RCA)
│   └── report_generator.py        # Executive health & incident report generator (MD, JSON, CSV)
│
├── logs/                          # Telemetry logs, alerts.log, and incidents.json
├── reports/                       # Generated Markdown, JSON, and CSV incident reports
└── tests/
    ├── test_metrics.py            # Unit tests for metrics collection & conversion
    ├── test_alerts.py             # Unit tests for threshold triggers & alert resolution
    └── test_incidents.py          # Unit tests for incident deduplication & report export
```

---

## 🐧 Dedicated Linux Server Installation

To monitor a dedicated Ubuntu / Debian Linux server or virtual machine:

```bash
# 1. Clone repository
git clone https://github.com/27Aditi/ServerWatch.git
cd ServerWatch

# 2. Install dependencies
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git tar gzip curl
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Grant execute permissions to Bash scripts
chmod +x scripts/*.sh automation/*.sh

# 4. Run local dashboard
streamlit run app.py
```

---

## 📜 Administration Scripts & Cron Scheduling

When running on a dedicated Linux host:
```bash
# Hardware & OS info:
bash scripts/system_info.sh

# Disk usage check:
bash scripts/disk_monitor.sh 85

# Top processes:
bash scripts/process_monitor.sh 10

# Safe log cleanup dry-run:
bash scripts/log_cleanup.sh --days 7 --dir logs --dry-run

# Confirmed live cleanup:
bash scripts/log_cleanup.sh --days 7 --dir logs --confirm

# systemd service audit:
bash scripts/service_monitor.sh

# Create timestamped tar.gz backup:
bash scripts/backup_logs.sh logs backups

# Install automated Cron jobs:
bash automation/cron_setup.sh --install
```

---

## 🧪 Testing

Execute the automated test suite covering all modules:
```bash
python run_tests.py
```
All 15 tests validate telemetry calculations, threshold logic, incident lifecycle states, and report generation.

---

## 📄 License

This project is licensed under the MIT License.

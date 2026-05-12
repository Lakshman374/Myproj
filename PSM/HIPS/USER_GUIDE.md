# HIPS User Guide - Complete Tutorial

This comprehensive guide will teach you how to use, configure, and create custom detection rules for the HIPS (Host-based Intrusion Prevention System).

## Table of Contents

1. [Getting Started](#getting-started)
2. [Understanding Rules](#understanding-rules)
3. [Creating Your First Rule](#creating-your-first-rule)
4. [Rule Examples](#rule-examples)
5. [Testing Rules](#testing-rules)
6. [Advanced Features](#advanced-features)
7. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Starting HIPS

#### 1. Start the Backend

```bash
cd /home/sk/workspace/qriocity/cyber/HIPS/backend
python -m hips_service.main
```

**Expected Output:**
```
============================================================
HIPS - Host-based Intrusion Prevention System
============================================================
Platform: linux
Initializing database...
Initializing rule engine...
Loading rules from /path/to/rules
Loaded 1 rules
Process monitor initialized
Filesystem monitor initialized
All components started successfully
API server starting on 0.0.0.0:8000
```

#### 2. Start the Frontend

In a new terminal:

```bash
cd /home/sk/workspace/qriocity/cyber/HIPS/frontend
npm run dev
```

**Expected Output:**
```
VITE v5.0.11  ready in 500ms
➜  Local:   http://localhost:5173/
```

#### 3. Access the Dashboard

Open your browser to: **http://localhost:5173**

---

## Understanding Rules

### What is a Rule?

A rule tells HIPS what to look for and what to do when it finds it. Rules are written in YAML format and consist of:

1. **Metadata**: Information about the rule (ID, name, severity)
2. **Conditions**: What events to match
3. **Actions**: What to do when matched

### Rule Structure

```yaml
rule:
  # METADATA
  id: "unique-rule-id"
  name: "Human Readable Name"
  description: "What this rule detects"
  enabled: true
  severity: "high"  # low, medium, high, critical
  category: "malware"  # malware, ransomware, persistence, etc.

  # CONDITIONS
  conditions:
    event_type: "process_create"  # or file_modify, network_connect, etc.
    platform:
      - "linux"
      - "windows"

    # ANY of these conditions match (OR)
    any:
      - field: "process_name"
        operator: "equals"
        value: "malware.exe"

    # ALL of these conditions must match (AND)
    all:
      - field: "process_path"
        operator: "contains"
        value: "/tmp"

  # ACTIONS
  actions:
    - type: "alert"
      priority: "high"
      message: "Suspicious activity detected"

    - type: "block_process"
      target: "process_pid"

  # OPTIONAL METADATA
  metadata:
    author: "Your Name"
    created: "2025-01-15"
    tags: ["malware", "detection"]
    references:
      - "https://attack.mitre.org/techniques/T1059/"
```

### Event Types

HIPS monitors these event types:

| Event Type | Description | Available Fields |
|------------|-------------|------------------|
| `process_create` | New process started | `process_name`, `process_pid`, `process_path`, `process_cmdline`, `parent_pid`, `user` |
| `process_terminate` | Process ended | `process_name`, `process_pid`, `process_path` |
| `file_create` | File created | `file_path`, `process_name`, `process_pid` |
| `file_modify` | File modified | `file_path`, `process_name`, `process_pid` |
| `file_delete` | File deleted | `file_path`, `process_name`, `process_pid` |
| `network_connect` | Network connection | `dst_ip`, `dst_port`, `protocol`, `process_name` |

### Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `equals` | Exact match | `value: "nc"` |
| `not_equals` | Not equal to | `value: "chrome"` |
| `in` | Value in list | `value: ["nc", "netcat"]` |
| `not_in` | Not in list | `value: ["chrome", "firefox"]` |
| `contains` | Substring match | `value: "powershell"` |
| `not_contains` | Does not contain | `value: "/safe"` |
| `regex` | Regex pattern | `value: "^malware.*\\.exe$"` |
| `greater_than` | Numeric > | `value: 1000` |
| `less_than` | Numeric < | `value: 100` |

### Actions

| Action Type | Description | Parameters |
|-------------|-------------|------------|
| `alert` | Create dashboard alert | `priority`, `message` |
| `log` | Log the event | None |
| `block_process` | Kill the process | `target` (field containing PID) |
| `notify` | Send notification | `message` |

---

## Creating Your First Rule

Let's create a simple rule that detects when someone runs Python scripts.

### Step 1: Create the Rule File

Create a new file in the `backend/rules/` directory:

```bash
cd /home/sk/workspace/qriocity/cyber/HIPS/backend/rules
nano python-script-detection.yaml
```

### Step 2: Write the Rule

```yaml
rule:
  id: "python-script-detection"
  name: "Python Script Execution"
  description: "Detects when Python scripts are executed"
  enabled: true
  severity: "low"
  category: "monitoring"

  conditions:
    event_type: "process_create"
    platform:
      - "linux"
      - "windows"

    any:
      - field: "process_name"
        operator: "equals"
        value: "python"

      - field: "process_name"
        operator: "equals"
        value: "python3"

      - field: "process_cmdline"
        operator: "contains"
        value: ".py"

  actions:
    - type: "alert"
      priority: "low"
      message: "Python script executed: {process_cmdline}"

    - type: "log"

  metadata:
    author: "HIPS User"
    created: "2025-01-15"
    tags: ["python", "monitoring"]
```

### Step 3: Reload Rules

You have two options:

**Option A: Restart the backend**
```bash
# Press Ctrl+C to stop, then restart
python -m hips_service.main
```

**Option B: Use the API (if implemented)**
```bash
curl -X POST http://localhost:8000/api/rules/reload
```

### Step 4: Test the Rule

Run a Python script:

```bash
python3 -c "print('Hello HIPS')"
```

### Step 5: Check the Alert

1. Open http://localhost:5173
2. Navigate to **Alerts** page
3. You should see an alert: "Python script executed: python3 -c print('Hello HIPS')"

---

## Rule Examples

### Example 1: Detect Netcat Usage (Network Tool)

**File:** `backend/rules/netcat-detection.yaml`

```yaml
rule:
  id: "netcat-usage-detection"
  name: "Netcat Network Tool Detection"
  description: "Detects use of netcat, a common hacking tool"
  enabled: true
  severity: "high"
  category: "malware"

  conditions:
    event_type: "process_create"
    platform:
      - "linux"
      - "windows"

    any:
      - field: "process_name"
        operator: "in"
        value: ["nc", "netcat", "ncat", "nc.traditional"]

  actions:
    - type: "alert"
      priority: "high"
      message: "Netcat detected! Process: {process_name}, Command: {process_cmdline}"

    - type: "block_process"
      target: "process_pid"

  metadata:
    author: "Security Team"
    created: "2025-01-15"
    tags: ["netcat", "network-tool", "hacking"]
    references:
      - "https://attack.mitre.org/techniques/T1059/"
```

**Test:**
```bash
# Install netcat if needed
sudo apt-get install netcat

# Try to run it (will be blocked!)
nc -l 1234
```

### Example 2: Ransomware Simulation Detection

**File:** `backend/rules/ransomware-rapid-encryption.yaml`

```yaml
rule:
  id: "ransomware-rapid-file-changes"
  name: "Ransomware Rapid File Modification Detection"
  description: "Detects when a process rapidly modifies many files"
  enabled: true
  severity: "critical"
  category: "ransomware"

  conditions:
    event_type: "file_modify"
    platform:
      - "linux"
      - "windows"

    # Trigger if 30 files modified in 60 seconds by same process
    frequency:
      count: 30
      timeframe: "60s"
      field: "process_pid"

  actions:
    - type: "alert"
      priority: "critical"
      message: "RANSOMWARE DETECTED! Process {process_name} (PID: {process_pid}) modified {count} files rapidly"

    - type: "block_process"
      target: "process_pid"

  metadata:
    author: "Security Team"
    created: "2025-01-15"
    tags: ["ransomware", "file-encryption", "critical"]
    references:
      - "https://attack.mitre.org/techniques/T1486/"
```

**Test:**
```bash
# Create test directory
mkdir -p /tmp/ransomware_test
cd /tmp/ransomware_test

# Simulate ransomware (rapid file changes)
for i in {1..40}; do
    echo "encrypted_data_$i" > file_$i.txt
    sleep 1
done
```

### Example 3: Suspicious PowerShell Detection (Windows)

**File:** `backend/rules/suspicious-powershell.yaml`

```yaml
rule:
  id: "encoded-powershell-detection"
  name: "Encoded PowerShell Command Detection"
  description: "Detects PowerShell with encoded commands (common malware technique)"
  enabled: true
  severity: "high"
  category: "malware"

  conditions:
    event_type: "process_create"
    platform:
      - "windows"

    all:
      - field: "process_name"
        operator: "contains"
        value: "powershell"

      - field: "process_cmdline"
        operator: "regex"
        value: "-(e|enc|encoded|encodedcommand)"

  actions:
    - type: "alert"
      priority: "high"
      message: "Encoded PowerShell detected: {process_cmdline}"

    - type: "block_process"
      target: "process_pid"

  metadata:
    author: "Security Team"
    created: "2025-01-15"
    tags: ["powershell", "malware", "obfuscation"]
    references:
      - "https://attack.mitre.org/techniques/T1059/001/"
```

### Example 4: Suspicious File Extension Change

**File:** `backend/rules/file-extension-ransomware.yaml`

```yaml
rule:
  id: "suspicious-file-extensions"
  name: "Ransomware File Extension Detection"
  description: "Detects common ransomware file extensions"
  enabled: true
  severity: "critical"
  category: "ransomware"

  conditions:
    event_type: "file_create"
    platform:
      - "linux"
      - "windows"

    any:
      - field: "file_path"
        operator: "regex"
        value: "\\.(encrypted|locked|crypto|cerber|locky|wannacry)$"

  actions:
    - type: "alert"
      priority: "critical"
      message: "Ransomware extension detected: {file_path}"

    - type: "block_process"
      target: "process_pid"

  metadata:
    author: "Security Team"
    tags: ["ransomware", "file-extension"]
```

**Test:**
```bash
# Create a file with ransomware extension
touch /tmp/important_document.txt.encrypted
```

### Example 5: SSH Brute Force Detection

**File:** `backend/rules/ssh-bruteforce.yaml`

```yaml
rule:
  id: "ssh-failed-login-attempts"
  name: "SSH Brute Force Detection"
  description: "Detects multiple SSH connection attempts (brute force)"
  enabled: true
  severity: "high"
  category: "intrusion"

  conditions:
    event_type: "process_create"
    platform:
      - "linux"

    all:
      - field: "process_name"
        operator: "equals"
        value: "sshd"

    frequency:
      count: 10
      timeframe: "60s"
      field: "dst_ip"

  actions:
    - type: "alert"
      priority: "high"
      message: "Possible SSH brute force from {dst_ip}"

    - type: "log"

  metadata:
    author: "Security Team"
    tags: ["ssh", "brute-force", "intrusion"]
```

---

## Testing Rules

### Test Methodology

1. **Create the rule** in `backend/rules/`
2. **Restart HIPS** backend
3. **Trigger the event** that matches the rule
4. **Verify the alert** in the dashboard

### Creating Test Scripts

#### Test Script 1: Process Creation Test

**File:** `test_process.sh`

```bash
#!/bin/bash
echo "Testing process creation detection..."

# Test 1: Python script
python3 -c "print('Test 1: Python execution')"
sleep 2

# Test 2: Netcat (if you want to test blocking)
# nc -l 1234  # This will be blocked!
# sleep 2

# Test 3: Multiple processes
for i in {1..5}; do
    sleep 0.5 &
done
wait

echo "Process tests complete!"
```

Run:
```bash
chmod +x test_process.sh
./test_process.sh
```

#### Test Script 2: File Activity Test

**File:** `test_files.py`

```python
#!/usr/bin/env python3
"""Test file monitoring and ransomware detection."""

import os
import time
from pathlib import Path

# Create test directory
test_dir = Path("/tmp/hips_file_test")
test_dir.mkdir(exist_ok=True)

print("Test 1: Normal file creation (should log but not alert)")
for i in range(5):
    file_path = test_dir / f"normal_file_{i}.txt"
    file_path.write_text(f"Normal content {i}")
    time.sleep(2)

print("\nTest 2: Rapid file changes (should trigger ransomware alert)")
for i in range(40):
    file_path = test_dir / f"rapid_file_{i}.txt"
    file_path.write_text(f"Encrypted content {i}")
    time.sleep(0.8)  # 40 files in ~32 seconds

print("\nTest 3: Ransomware extensions (should trigger alert)")
(test_dir / "document.txt.encrypted").write_text("encrypted")
time.sleep(1)
(test_dir / "photo.jpg.locked").write_text("locked")
time.sleep(1)

print("\nFile tests complete! Check the Alerts page.")
```

Run:
```bash
chmod +x test_files.py
./test_files.py
```

#### Test Script 3: Complete Test Suite

**File:** `test_all.sh`

```bash
#!/bin/bash

echo "============================================"
echo "HIPS Complete Test Suite"
echo "============================================"
echo ""

# Test 1: Process monitoring
echo "[Test 1] Process Monitoring"
python3 -c "print('Testing process detection')"
sleep 2

# Test 2: File creation
echo "[Test 2] File Creation"
mkdir -p /tmp/hips_test
echo "test data" > /tmp/hips_test/test1.txt
sleep 2

# Test 3: Rapid file changes (ransomware simulation)
echo "[Test 3] Ransomware Simulation (40 files in 30 seconds)"
cd /tmp/hips_test
for i in {1..40}; do
    echo "data $i" > rapid_$i.txt
    sleep 0.75
done

# Test 4: Suspicious file extension
echo "[Test 4] Suspicious File Extension"
touch /tmp/hips_test/important.doc.encrypted
sleep 2

echo ""
echo "============================================"
echo "All tests complete!"
echo "Check http://localhost:5173 for alerts"
echo "============================================"
```

Run:
```bash
chmod +x test_all.sh
./test_all.sh
```

### Verifying Detection

After running tests:

1. **Dashboard** (http://localhost:5173)
   - Check real-time event counts

2. **Alerts Page**
   - Look for new alerts
   - Check severity levels
   - View alert details

3. **Logs Page**
   - See all events (process, file, network)
   - Filter by event type
   - Search for specific activities

4. **Backend Terminal**
   - Watch for log messages:
     ```
     Rule matched: python-script-detection - Python Script Execution
     Alert created: Python script executed...
     ```

---

## Advanced Features

### Frequency-Based Detection

Detect patterns over time (like brute force attacks):

```yaml
conditions:
  event_type: "process_create"

  frequency:
    count: 50        # Number of events
    timeframe: "60s" # Within this time
    field: "dst_ip"  # Group by this field
```

**Timeframe formats:**
- `60s` - 60 seconds
- `5m` - 5 minutes
- `1h` - 1 hour
- `1d` - 1 day

### Regex Patterns

Use regex for complex matching:

```yaml
- field: "file_path"
  operator: "regex"
  value: "^/tmp/.*\\.exe$"  # .exe files in /tmp
```

### Complex Conditions

Combine AND and OR logic:

```yaml
conditions:
  event_type: "process_create"

  # ALL of these must match
  all:
    - field: "process_name"
      operator: "equals"
      value: "python3"

    - field: "user"
      operator: "equals"
      value: "root"

  # AND any of these must match
  any:
    - field: "process_cmdline"
      operator: "contains"
      value: "exploit"

    - field: "process_cmdline"
      operator: "contains"
      value: "reverse_shell"
```

### Message Templates

Use placeholders in alert messages:

```yaml
actions:
  - type: "alert"
    message: "User {user} ran {process_name} from {process_path}"
```

Available placeholders are any fields from the event data.

---

## Troubleshooting

### Rule Not Loading

**Problem:** Rule doesn't appear in dashboard

**Solutions:**
1. Check YAML syntax:
   ```bash
   python3 -c "import yaml; yaml.safe_load(open('your-rule.yaml'))"
   ```

2. Check backend logs:
   ```
   ERROR - Error parsing rule file: ...
   ```

3. Ensure rule is in `backend/rules/` directory

4. Restart backend

### Rule Not Triggering

**Problem:** Events happen but no alert

**Debug steps:**

1. **Check rule is enabled:**
   ```yaml
   enabled: true
   ```

2. **Verify event type matches:**
   - Rule: `event_type: "process_create"`
   - Event: Must be process creation

3. **Check platform:**
   ```yaml
   platform:
     - "linux"  # Make sure your OS is listed
   ```

4. **Test conditions manually:**
   - Look at the event in Logs page
   - Verify field values match your conditions

5. **Check backend logs:**
   ```
   INFO - Rule matched: your-rule-id
   ```

### Permission Errors

**Problem:** Process blocking fails

**Solution:**
```bash
# Run with sudo on Linux
sudo python -m hips_service.main
```

### Database Locked

**Problem:** SQLite database locked

**Solution:**
```bash
# Stop backend, delete database, restart
cd backend
rm hips_data.db
python -m hips_service.main
```

---

## Best Practices

### Rule Writing

1. **Use descriptive IDs:** `ransomware-wannacry-detection` not `rule1`
2. **Add metadata:** Help others understand your rules
3. **Test thoroughly:** Don't deploy untested rules
4. **Start with logs:** Use `log` action before `block_process`
5. **Use appropriate severity:** Don't make everything `critical`

### Testing

1. **Use test directories:** `/tmp/hips_test` not production folders
2. **Test in isolation:** One rule at a time
3. **Document tests:** Create test scripts for each rule
4. **Monitor backend logs:** Watch for errors

### Security

1. **Review before blocking:** Ensure rule accuracy before using `block_process`
2. **Whitelist safe processes:** Use `not_in` to exclude known-good processes
3. **Tune frequency thresholds:** Avoid false positives
4. **Keep rules updated:** Review and update regularly

---

## Quick Reference Card

### Common Rule Patterns

**Detect specific process:**
```yaml
any:
  - field: "process_name"
    operator: "equals"
    value: "malware.exe"
```

**Detect command line pattern:**
```yaml
any:
  - field: "process_cmdline"
    operator: "contains"
    value: "suspicious_string"
```

**Detect file in directory:**
```yaml
all:
  - field: "file_path"
    operator: "contains"
    value: "/tmp/"
```

**Detect rapid activity:**
```yaml
frequency:
  count: 50
  timeframe: "60s"
  field: "process_pid"
```

### File Locations

- **Rules:** `/home/sk/workspace/qriocity/cyber/HIPS/backend/rules/`
- **Config:** `/home/sk/workspace/qriocity/cyber/HIPS/backend/config/`
- **Database:** `/home/sk/workspace/qriocity/cyber/HIPS/backend/hips_data.db`
- **Logs:** `/home/sk/workspace/qriocity/cyber/HIPS/backend/hips.log`

### API Endpoints

- **Alerts:** http://localhost:8000/api/alerts
- **Logs:** http://localhost:8000/api/logs
- **Rules:** http://localhost:8000/api/rules
- **System:** http://localhost:8000/api/system/status

---

## Next Steps

1. **Create your first rule** following the examples
2. **Test it** using the provided test scripts
3. **Refine detection** based on results
4. **Share rules** with your team
5. **Monitor regularly** and tune as needed

Happy detecting! 🛡️

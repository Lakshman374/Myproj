# HIPS - Host-Based Intrusion Prevention System

A cross-platform Host-Based Intrusion Prevention System with real-time monitoring, rule-based detection, and a modern web dashboard.

## Features

- **Cross-Platform Support**: Works on both Linux and Windows
- **Real-Time Monitoring**:
  - Process monitoring (creation, termination, suspicious executables)
  - File system monitoring (ransomware detection, rapid file changes)
  - Network monitoring (connections, suspicious ports)
  - Registry monitoring (Windows only - persistence detection)
- **Rule-Based Detection**: YAML-based rules with support for complex conditions
- **Web Dashboard**: Modern React UI with real-time updates
- **Alerting System**: Real-time alerts for suspicious activity
- **Process Blocking**: Automatically terminate malicious processes

## Architecture

### Backend (Python)
- **FastAPI**: REST API and WebSocket server
- **SQLAlchemy**: Database ORM (SQLite)
- **psutil**: Cross-platform process and system monitoring
- **watchdog**: File system monitoring
- **Event Bus**: Async event processing architecture

### Frontend (React + TypeScript)
- **React 18**: Modern UI library
- **Vite**: Fast build tool
- **ShadCN UI**: Beautiful, accessible components
- **Tailwind CSS**: Utility-first styling
- **TanStack Query**: Data fetching and caching

## Installation

### Prerequisites

**Backend:**
- Python 3.9+
- pip

**Frontend:**
- Node.js 18+
- npm or yarn

### Backend Setup

1. Navigate to backend directory:
```bash
cd backend
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. (Optional) Create and configure `config/hips_config.yaml` if you want custom settings

### Frontend Setup

1. Navigate to frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

## Running the Application

### Start Backend

From the `backend` directory:

```bash
python -m hips_service.main
```

The backend will start on `http://localhost:8000`

**Note**: On Linux, you may need to run with `sudo` for full process monitoring capabilities:
```bash
sudo python -m hips_service.main
```

### Start Frontend

From the `frontend` directory:

```bash
npm run dev
```

The frontend will start on `http://localhost:5173`

## Usage

1. Open your browser and go to `http://localhost:5173`
2. You'll see the dashboard with real-time metrics
3. The system will automatically start monitoring:
   - Process creation/termination
   - File system changes
   - Network connections

## Creating Rules

Rules are defined in YAML format and stored in `backend/rules/`.

### Example Rule

```yaml
rule:
  id: "example-rule"
  name: "Detect Suspicious Process"
  description: "Alerts on suspicious process execution"
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
        operator: "equals"
        value: "malware.exe"

  actions:
    - type: "alert"
      priority: "high"
    - type: "block_process"
      target: "process_pid"
```

### Rule Operators

- `equals` / `not_equals`: Exact match
- `in` / `not_in`: Value in list
- `contains` / `not_contains`: Substring match
- `regex`: Regular expression match
- `greater_than` / `less_than`: Numeric comparison

### Rule Actions

- `alert`: Create an alert in the dashboard
- `log`: Log the event
- `block_process`: Terminate the process
- `notify`: Send notification (placeholder)

## Demo Scenarios

### Ransomware Detection Test

Create a test script that rapidly modifies files:

```python
# test_ransomware.py
import time
import os

test_dir = "/tmp/hips_test"
os.makedirs(test_dir, exist_ok=True)

for i in range(60):
    with open(f"{test_dir}/file_{i}.txt", "w") as f:
        f.write(f"test {i}")
    time.sleep(0.5)
```

Run the script and watch HIPS detect the rapid file changes!

### Suspicious Process Test

The system will alert when it detects processes like `nc`, `netcat`, or encoded PowerShell commands.

## Project Structure

```
HIPS/
├── backend/
│   ├── hips_service/
│   │   ├── core/           # Platform detection, event bus, config
│   │   ├── monitors/       # Process, file, network monitors
│   │   ├── rules/          # Rule engine
│   │   ├── database/       # Database models
│   │   ├── api/            # FastAPI routes
│   │   └── main.py         # Entry point
│   ├── rules/              # YAML rule files
│   └── config/             # Configuration
│
└── frontend/
    ├── src/
    │   ├── components/     # React components
    │   ├── pages/          # Page components
    │   ├── services/       # API services
    │   └── types/          # TypeScript types
    └── package.json
```

## Configuration

Edit `backend/config/hips_config.yaml` to customize:

- Monitoring intervals
- Watched file paths
- Network ports to monitor
- Database location
- API server settings

## Development

### Backend

The backend uses asyncio for concurrent monitoring. Main components:

- **EventBus**: Central event distribution
- **Monitors**: Detect system events
- **RuleEngine**: Match events against rules
- **FastAPI**: Expose REST API and WebSocket

### Frontend

The frontend is built with React + TypeScript:

- **Pages**: Dashboard, Alerts, Logs, Rules, Monitoring
- **Components**: Reusable UI components (ShadCN UI)
- **Services**: API communication layer
- **Real-time**: WebSocket for live updates

## Troubleshooting

### Permission Errors (Linux)

Run with sudo for full monitoring capabilities:
```bash
sudo python -m hips_service.main
```

### Port Already in Use

Change the API port in `backend/config/hips_config.yaml`:
```yaml
api:
  port: 8001  # Change to any available port
```

### Database Locked

Stop the backend, delete `hips_data.db`, and restart.

## Future Enhancements (Phase 2+)

- [ ] Visual rule builder in frontend
- [ ] Network packet capture
- [ ] Machine learning anomaly detection
- [ ] SIEM integration
- [ ] Email/Slack notifications
- [ ] Report generation
- [ ] Multi-host management

## License

MIT License - Educational/College Project

## Credits

Built as a college project demonstrating:
- Cross-platform system monitoring
- Real-time event processing
- Modern web development (React + FastAPI)
- Security tool development

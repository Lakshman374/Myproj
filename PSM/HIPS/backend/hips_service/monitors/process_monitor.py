"""Cross-platform process monitoring using psutil."""

import asyncio
import psutil
from typing import List, Dict, Set
from datetime import datetime
import logging

from hips_service.monitors.base_monitor import BaseMonitor
from hips_service.core.event_bus import EventBus, MonitorEvent
from hips_service.core.platform_detector import PlatformDetector
from hips_service.utils.time import get_local_time

logger = logging.getLogger(__name__)


class ProcessMonitor(BaseMonitor):
    """Monitor process creation and termination using psutil."""

    def __init__(self, event_bus: EventBus, interval: float = 2.0):
        """Initialize process monitor.

        Args:
            event_bus: Event bus for publishing events
            interval: Monitoring interval in seconds
        """
        super().__init__(event_bus, "ProcessMonitor")
        self.interval = interval
        self._known_pids: Set[int] = set()
        self._process_info: Dict[int, Dict] = {}
        self._excluded_processes: Set[str] = set()

    def get_capabilities(self) -> List[str]:
        """Get monitoring capabilities.

        Returns:
            List of capabilities
        """
        return [
            "process_create",
            "process_terminate",
            "process_info"
        ]

    def update_interval(self, seconds: float):
        """Update the polling interval at runtime (takes effect on next loop cycle).

        Args:
            seconds: New interval in seconds
        """
        logger.info(f"ProcessMonitor interval updated: {self.interval}s -> {seconds}s")
        self.interval = seconds

    def update_excluded_processes(self, names: list):
        """Update the set of process names to suppress from event emission.

        Args:
            names: List of process name strings (e.g. ['systemd', 'kworker'])
        """
        self._excluded_processes = {n.strip() for n in names if n.strip()}
        logger.info(f"ProcessMonitor excluded processes: {self._excluded_processes}")

    async def start(self):
        """Start process monitoring."""
        if self.running:
            logger.warning(f"{self.name} already running")
            return

        self.running = True
        logger.info(f"{self.name} starting on {PlatformDetector.get_platform_name()}")

        # Get initial process list
        self._initialize_process_list()

        # stop() may have been called during initialization — don't create the task
        if not self.running:
            return

        # Start monitoring loop
        self._monitor_task = asyncio.create_task(self._monitoring_loop())

    async def stop(self):
        """Stop process monitoring."""
        if not self.running:
            return

        self.running = False
        logger.info(f"{self.name} stopping")

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

    def _initialize_process_list(self):
        """Initialize the list of known processes."""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline', 'create_time']):
                try:
                    self._known_pids.add(proc.pid)
                    self._process_info[proc.pid] = proc.info
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            logger.info(f"{self.name} initialized with {len(self._known_pids)} processes")
        except Exception as e:
            logger.error(f"Error initializing process list: {e}")

    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                await self._check_processes()
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                await asyncio.sleep(self.interval)

    async def _check_processes(self):
        """Check for new and terminated processes."""
        current_pids = set()

        try:
            # Get current processes
            for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline', 'ppid', 'username', 'create_time']):
                try:
                    pid = proc.pid
                    current_pids.add(pid)

                    # Check for new process
                    if pid not in self._known_pids:
                        await self._handle_process_create(proc)
                        self._known_pids.add(pid)
                        self._process_info[pid] = proc.info

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # Check for terminated processes
            terminated_pids = self._known_pids - current_pids
            for pid in terminated_pids:
                await self._handle_process_terminate(pid)
                self._known_pids.discard(pid)
                self._process_info.pop(pid, None)

        except Exception as e:
            logger.error(f"Error checking processes: {e}")

    async def _handle_process_create(self, proc: psutil.Process):
        """Handle process creation event.

        Args:
            proc: Process object
        """
        try:
            info = proc.info
            process_name = info.get('name', 'unknown')

            if process_name in self._excluded_processes:
                return

            process_exe = info.get('exe', '')
            cmdline = info.get('cmdline', [])
            cmdline_str = ' '.join(cmdline) if cmdline else ''

            # Determine severity based on process characteristics
            severity = self._determine_severity(process_name, process_exe, cmdline_str)

            event = MonitorEvent(
                timestamp=get_local_time(),
                event_type="process_create",
                platform=PlatformDetector.get_platform_name(),
                severity=severity,
                data={
                    'process_name': process_name,
                    'process_pid': proc.pid,
                    'process_path': process_exe,
                    'process_cmdline': cmdline_str,
                    'parent_pid': info.get('ppid'),
                    'user': info.get('username', 'unknown'),
                    'create_time': info.get('create_time')
                }
            )

            await self.publish_event(event)

        except Exception as e:
            logger.error(f"Error handling process create: {e}")

    async def _handle_process_terminate(self, pid: int):
        """Handle process termination event.

        Args:
            pid: Process ID
        """
        try:
            info = self._process_info.get(pid, {})

            event = MonitorEvent(
                timestamp=get_local_time(),
                event_type="process_terminate",
                platform=PlatformDetector.get_platform_name(),
                severity="low",
                data={
                    'process_name': info.get('name', 'unknown'),
                    'process_pid': pid,
                    'process_path': info.get('exe', ''),
                }
            )

            await self.publish_event(event)

        except Exception as e:
            logger.error(f"Error handling process terminate: {e}")

    def _determine_severity(self, name: str, exe: str, cmdline: str) -> str:
        """Determine event severity based on process characteristics.

        Args:
            name: Process name
            exe: Executable path
            cmdline: Command line

        Returns:
            Severity level
        """
        # Simple heuristics for demonstration
        # Handle None values safely
        name_lower = name.lower() if name else ''
        exe_lower = exe.lower() if exe else ''
        cmdline_lower = cmdline.lower() if cmdline else ''

        # High severity indicators
        suspicious_names = ['nc', 'netcat', 'ncat', 'socat', 'mimikatz', 'psexec']
        suspicious_patterns = ['powershell -enc', 'cmd /c', 'wget http', 'curl http']

        if any(s in name_lower for s in suspicious_names):
            return "high"

        if any(pattern in cmdline_lower for pattern in suspicious_patterns):
            return "medium"

        return "low"

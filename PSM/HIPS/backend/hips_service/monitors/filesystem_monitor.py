"""Cross-platform file system monitoring using watchdog."""

import asyncio
import os
from typing import List, Dict
from datetime import datetime, timedelta
from collections import defaultdict, deque
from pathlib import Path
import logging

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from hips_service.monitors.base_monitor import BaseMonitor
from hips_service.core.event_bus import EventBus, MonitorEvent
from hips_service.core.platform_detector import PlatformDetector
from hips_service.utils.time import get_local_time

logger = logging.getLogger(__name__)


class FilesystemEventHandler(FileSystemEventHandler):
    """Handler for filesystem events."""

    def __init__(self, callback, loop):
        """Initialize handler.

        Args:
            callback: Async callback function for events
            loop: The event loop to run callbacks on
        """
        super().__init__()
        self.callback = callback
        self.loop = loop

    def on_created(self, event: FileSystemEvent):
        """Handle file/directory creation."""
        if not event.is_directory:
            asyncio.run_coroutine_threadsafe(
                self.callback('created', event.src_path),
                self.loop
            )

    def on_modified(self, event: FileSystemEvent):
        """Handle file/directory modification."""
        if not event.is_directory:
            asyncio.run_coroutine_threadsafe(
                self.callback('modified', event.src_path),
                self.loop
            )

    def on_deleted(self, event: FileSystemEvent):
        """Handle file/directory deletion."""
        if not event.is_directory:
            asyncio.run_coroutine_threadsafe(
                self.callback('deleted', event.src_path),
                self.loop
            )

    def on_moved(self, event: FileSystemEvent):
        """Handle file/directory move."""
        if not event.is_directory:
            asyncio.run_coroutine_threadsafe(
                self.callback('moved', event.src_path, event.dest_path),
                self.loop
            )


class FilesystemMonitor(BaseMonitor):
    """Monitor filesystem changes using watchdog."""

    # Suspicious file extensions (ransomware indicators)
    SUSPICIOUS_EXTENSIONS = {
        '.encrypted', '.locked', '.crypto', '.crypted', '.enc',
        '.crypt', '.locky', '.cerber', '.zepto', '.osiris',
        '.wannacry', '.wcry', '.wncry', '.wncryt', '.zzzzz',
        '.crysis', '.dharma', '.wallet', '.onion'
    }

    # Extensions that are internal/system files and should never trigger alerts
    EXCLUDED_EXTENSIONS = {
        '.db', '.db-journal', '.db-shm', '.db-wal',  # SQLite internals
        '.log',  # Log files written by this service
        '.tmp', '.swp',  # Temp/editor swap files
        '.pyc',  # Python bytecode
    }

    def __init__(self, event_bus: EventBus, watched_paths: List[str] = None,
                 excluded_paths: List[str] = None,
                 rapid_change_threshold: int = 50, rapid_change_window: int = 60):
        """Initialize filesystem monitor.

        Args:
            event_bus: Event bus for publishing events
            watched_paths: List of paths to monitor
            excluded_paths: List of path prefixes to exclude from monitoring
            rapid_change_threshold: Number of changes to trigger alert
            rapid_change_window: Time window in seconds for rapid changes
        """
        super().__init__(event_bus, "FilesystemMonitor")
        self.watched_paths = watched_paths or self._get_default_paths()
        self.rapid_change_threshold = rapid_change_threshold
        self.rapid_change_window = rapid_change_window

        # Always exclude the backend directory itself to prevent self-monitoring
        default_excluded = [str(Path(__file__).parent.parent.parent)]
        self.excluded_paths = [os.path.normcase(p) for p in (excluded_paths or []) + default_excluded]

        self.observer = None
        self._event_handler = None
        self._loop = None

        # Track file changes for rapid modification detection
        self._file_changes: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        # Avoid flooding debug logs for frequently ignored files (e.g. SQLite journals)
        self._excluded_log_times: Dict[str, datetime] = {}
        self._excluded_log_cooldown = timedelta(seconds=60)

    def get_capabilities(self) -> List[str]:
        """Get monitoring capabilities.

        Returns:
            List of capabilities
        """
        return [
            "file_create",
            "file_modify",
            "file_delete",
            "file_move",
            "ransomware_detection"
        ]

    def _get_default_paths(self) -> List[str]:
        """Get default paths to monitor based on platform.

        Returns:
            List of default paths
        """
        if PlatformDetector.is_linux():
            home = Path.home()
            return [
                str(home / "Documents"),
                str(home / "Downloads"),
                str(home / "Desktop"),
            ]
        elif PlatformDetector.is_windows():
            home = Path.home()
            return [
                str(home / "Documents"),
                str(home / "Downloads"),
                str(home / "Desktop"),
            ]
        return []

    async def start(self):
        """Start filesystem monitoring."""
        if self.running:
            logger.warning(f"{self.name} already running")
            return

        self.running = True
        logger.info(f"{self.name} starting on {PlatformDetector.get_platform_name()}")

        # Get the running event loop
        self._loop = asyncio.get_running_loop()

        # Create event handler with the loop
        self._event_handler = FilesystemEventHandler(self._handle_fs_event, self._loop)

        # Create observer
        self.observer = Observer()

        # Schedule watching for each path
        scheduled = []
        for path in self.watched_paths:
            if not os.path.exists(path):
                logger.warning(f"Path does not exist, skipping: {path}")
                continue
            try:
                self.observer.schedule(self._event_handler, path, recursive=True)
                scheduled.append(path)
                logger.info(f"Watching path: {path}")
            except Exception as e:
                logger.warning(f"Cannot watch path (permission denied?): {path} — {e}")

        if not scheduled:
            logger.error("No watchable paths — filesystem monitor will not detect any events")
            return

        # Start observer
        try:
            self.observer.start()
        except Exception as e:
            logger.error(f"Filesystem observer failed to start: {e}", exc_info=True)

    async def stop(self):
        """Stop filesystem monitoring."""
        if not self.running:
            return

        self.running = False
        logger.info(f"{self.name} stopping")

        if self.observer:
            self.observer.stop()
            self.observer.join()

    async def update_watched_paths(self, new_paths: List[str]):
        """Swap watched paths at runtime by restarting the watchdog observer.

        Args:
            new_paths: New list of paths to watch
        """
        logger.info(f"FilesystemMonitor: updating watched paths to {new_paths}")
        self.watched_paths = new_paths

        # Stop the current observer
        if self.observer:
            self.observer.stop()
            self.observer.join()

        # Create and start a fresh observer with the new paths
        self.observer = Observer()
        self._event_handler = FilesystemEventHandler(self._handle_fs_event, self._loop)

        scheduled = []
        for path in self.watched_paths:
            if not os.path.exists(path):
                logger.warning(f"Path does not exist, skipping: {path}")
                continue
            try:
                self.observer.schedule(self._event_handler, path, recursive=True)
                scheduled.append(path)
                logger.info(f"Now watching path: {path}")
            except Exception as e:
                logger.warning(f"Cannot watch path (permission denied?): {path} — {e}")

        if scheduled:
            self.observer.start()
            logger.info("FilesystemMonitor: observer restarted with new paths")
        else:
            logger.error("No watchable paths after update — filesystem monitor inactive")

    def _is_excluded(self, file_path: str) -> bool:
        """Check if a file path should be excluded from monitoring.

        Args:
            file_path: File path to check

        Returns:
            True if excluded, False otherwise
        """
        # Check excluded extensions
        ext = os.path.splitext(file_path)[1].lower()
        if ext in self.EXCLUDED_EXTENSIONS:
            return True

        # Check excluded path prefixes
        normalized = os.path.normcase(file_path)
        for excluded in self.excluded_paths:
            if normalized.startswith(excluded):
                return True

        return False

    async def _handle_fs_event(self, event_type: str, src_path: str, dest_path: str = None):
        """Handle filesystem event.

        Args:
            event_type: Type of event (created, modified, deleted, moved)
            src_path: Source file path
            dest_path: Destination path (for move events)
        """
        try:
            # Skip files/paths that should never trigger alerts
            if self._is_excluded(src_path):
                self._log_excluded_path_once(src_path)
                return

            timestamp = get_local_time()

            # Check for suspicious extension
            is_suspicious = self._is_suspicious_extension(src_path)

            # Determine severity
            severity = self._determine_severity(event_type, src_path)

            # Track file modifications for rapid change detection
            if event_type in ('created', 'modified'):
                await self._track_file_change(src_path, timestamp)

            # Create event
            event = MonitorEvent(
                timestamp=timestamp,
                event_type=f"file_{event_type}",
                platform=PlatformDetector.get_platform_name(),
                severity=severity,
                data={
                    'file_path': src_path,
                    'file_operation': event_type,
                    'file_name': os.path.basename(src_path),
                    'file_extension': os.path.splitext(src_path)[1],
                    'dest_path': dest_path,
                    'is_suspicious_extension': is_suspicious
                }
            )

            await self.publish_event(event)

        except Exception as e:
            logger.error(f"Error handling filesystem event: {e}", exc_info=True)

    async def _track_file_change(self, file_path: str, timestamp: datetime):
        """Track file changes for rapid modification detection.

        Args:
            file_path: Path of changed file
            timestamp: Timestamp of change
        """
        # Get parent directory
        parent_dir = os.path.dirname(file_path)

        # Add timestamp to changes for this directory
        self._file_changes[parent_dir].append(timestamp)

        # Check for rapid changes
        changes = list(self._file_changes[parent_dir])
        if len(changes) < self.rapid_change_threshold:
            return

        # Count changes in time window
        cutoff = timestamp - timedelta(seconds=self.rapid_change_window)
        recent_changes = [t for t in changes if t >= cutoff]

        if len(recent_changes) >= self.rapid_change_threshold:
            # Possible ransomware detected!
            await self._trigger_ransomware_alert(parent_dir, len(recent_changes))

    async def _trigger_ransomware_alert(self, directory: str, change_count: int):
        """Trigger ransomware detection alert.

        Args:
            directory: Directory with rapid changes
            change_count: Number of changes detected
        """
        event = MonitorEvent(
            timestamp=get_local_time(),
            event_type="ransomware_detected",
            platform=PlatformDetector.get_platform_name(),
            severity="critical",
            data={
                'directory': directory,
                'change_count': change_count,
                'time_window_seconds': self.rapid_change_window,
                'threshold': self.rapid_change_threshold,
                'detection_reason': 'rapid_file_modifications'
            }
        )

        await self.publish_event(event)
        logger.critical(f"Ransomware detected in {directory}: {change_count} changes in {self.rapid_change_window}s")

    def _is_suspicious_extension(self, file_path: str) -> bool:
        """Check if file has suspicious extension.

        Args:
            file_path: File path to check

        Returns:
            True if suspicious, False otherwise
        """
        ext = os.path.splitext(file_path)[1].lower()
        return ext in self.SUSPICIOUS_EXTENSIONS

    def _determine_severity(self, event_type: str, file_path: str) -> str:
        """Determine event severity.

        Args:
            event_type: Type of filesystem event
            file_path: Path of affected file

        Returns:
            Severity level
        """
        # Check for suspicious extension
        if self._is_suspicious_extension(file_path):
            return "critical"

        # Deleted files are more suspicious
        if event_type == 'deleted':
            return "medium"

        return "low"

    def _log_excluded_path_once(self, file_path: str) -> None:
        """Rate-limit excluded path debug logging to reduce noise."""
        now = get_local_time()
        last_logged = self._excluded_log_times.get(file_path)
        if not last_logged or now - last_logged >= self._excluded_log_cooldown:
            logger.debug(f"Skipping excluded path: {file_path}")
            self._excluded_log_times[file_path] = now

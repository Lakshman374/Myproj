"""Activity logger for storing events to database."""

import asyncio
import logging
from datetime import datetime

from hips_service.core.event_bus import EventBus, MonitorEvent
from hips_service.database.models import ActivityLog, get_db

logger = logging.getLogger(__name__)


class ActivityLogger:
    """Logs monitoring events to database."""

    def __init__(self, event_bus: EventBus):
        """Initialize activity logger.

        Args:
            event_bus: Event bus to subscribe to
        """
        self.event_bus = event_bus
        self._running = False

    async def start(self):
        """Start activity logger."""
        if self._running:
            return

        self._running = True
        logger.info("Activity logger starting")

        # Subscribe to all events
        self.event_bus.subscribe('*', self.log_event)

        logger.info("Activity logger started")

    async def stop(self):
        """Stop activity logger."""
        self._running = False
        logger.info("Activity logger stopped")

    def _save_log_sync(self, log_entry: ActivityLog):
        """Save activity log entry synchronously (runs in thread pool)."""
        with get_db() as db:
            db.add(log_entry)
            db.commit()

    async def log_event(self, event: MonitorEvent):
        """Log event to database.

        Args:
            event: Event to log
        """
        try:
            # Create activity log entry
            log_entry = ActivityLog(
                timestamp=event.timestamp,
                event_type=event.event_type,
                platform=event.platform,
                severity=event.severity
            )

            # Map event data to log fields
            data = event.data

            # Process details
            if 'process_name' in data:
                log_entry.process_name = data.get('process_name')
            if 'process_pid' in data:
                log_entry.process_pid = data.get('process_pid')
            if 'process_path' in data:
                log_entry.process_path = data.get('process_path')
            if 'process_cmdline' in data:
                log_entry.process_cmdline = data.get('process_cmdline')
            if 'parent_pid' in data:
                log_entry.parent_pid = data.get('parent_pid')
            if 'user' in data:
                log_entry.user = data.get('user')

            # File details
            if 'file_path' in data:
                log_entry.file_path = data.get('file_path')
            if 'file_operation' in data:
                log_entry.file_operation = data.get('file_operation')

            # Network details
            if 'src_ip' in data:
                log_entry.src_ip = data.get('src_ip')
            if 'src_port' in data:
                log_entry.src_port = data.get('src_port')
            if 'dst_ip' in data:
                log_entry.dst_ip = data.get('dst_ip')
            if 'dst_port' in data:
                log_entry.dst_port = data.get('dst_port')
            if 'protocol' in data:
                log_entry.protocol = data.get('protocol')

            # Registry details (Windows)
            if 'registry_key' in data:
                log_entry.registry_key = data.get('registry_key')
            if 'registry_operation' in data:
                log_entry.registry_operation = data.get('registry_operation')
            if 'registry_value' in data:
                log_entry.registry_value = data.get('registry_value')

            # Save to database in thread pool to avoid blocking the event loop.
            # A single try/except covers both field mapping and DB errors so
            # nothing is swallowed silently.
            await asyncio.to_thread(self._save_log_sync, log_entry)
            logger.debug(f"Logged event: {event.event_type}")

        except Exception as e:
            logger.error(f"Error logging event {event.event_type}: {e}", exc_info=True)

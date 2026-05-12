"""Main entry point for CHIPS service."""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from hips_service.core.config import get_config
from hips_service.core.platform_detector import PlatformDetector
from hips_service.core.event_bus import get_event_bus
from hips_service.core.activity_logger import ActivityLogger
from hips_service.database.models import init_db
from hips_service.monitors.process_monitor import ProcessMonitor
from hips_service.monitors.filesystem_monitor import FilesystemMonitor
from hips_service.monitors.registry_monitor import RegistryMonitor
from hips_service.rules.engine import RuleEngine
from hips_service.api.app import create_app
from hips_service.api.routes import rules, system, websocket

# Configure logging
_log_level = getattr(logging, os.getenv('HIPS_LOG_LEVEL', 'INFO').upper(), logging.INFO)
logging.basicConfig(
    level=_log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        RotatingFileHandler(
            'hips.log',
            maxBytes=10 * 1024 * 1024,  # 10 MB per file
            backupCount=5               # keep 5 old files → 50 MB max total
        ),
    ]
)

logger = logging.getLogger(__name__)


class CHIPSService:
    """Main CHIPS service."""

    def __init__(self):
        """Initialize CHIPS service."""
        self.config = get_config()
        self.event_bus = get_event_bus()
        self.monitors = []
        self.rule_engine = None
        self.activity_logger = None
        self._cleanup_task = None

    async def initialize(self):
        """Initialize all components."""
        logger.info("="*60)
        logger.info("CHIPS - Intrusion Prevention System")
        logger.info("="*60)
        logger.info(f"Platform: {PlatformDetector.get_platform_name()}")

        # Check platform support
        if not PlatformDetector.is_supported():
            logger.error("Unsupported platform!")
            sys.exit(1)

        # Initialize database
        logger.info("Initializing database...")
        db_path = self.config.database.path
        init_db(f"sqlite:///{db_path}", echo=self.config.database.echo)

        # Create rules directory if it doesn't exist
        rules_dir = Path(self.config.rules_directory)
        rules_dir.mkdir(parents=True, exist_ok=True)

        # Initialize rule engine
        logger.info("Initializing rule engine...")
        self.rule_engine = RuleEngine(self.event_bus, str(rules_dir))

        # Initialize activity logger
        logger.info("Initializing activity logger...")
        self.activity_logger = ActivityLogger(self.event_bus)

        # Inject rule engine into routes
        rules.set_rule_engine(self.rule_engine)

        # Initialize monitors
        logger.info("Initializing monitors...")

        # Process monitor
        if self.config.process_monitoring.enabled:
            process_monitor = ProcessMonitor(
                self.event_bus,
                interval=self.config.process_monitoring.interval_seconds
            )
            self.monitors.append(process_monitor)
            logger.info("Process monitor initialized")

        # Filesystem monitor
        if self.config.file_monitoring.enabled:
            watched_paths = self.config.file_monitoring.watched_paths
            filesystem_monitor = FilesystemMonitor(
                self.event_bus,
                watched_paths=watched_paths if watched_paths else None,
                rapid_change_threshold=self.config.file_monitoring.rapid_change_threshold,
                rapid_change_window=self.config.file_monitoring.rapid_change_window_seconds
            )
            # Apply excluded extensions from config — validate before adding
            if hasattr(self.config.file_monitoring, 'excluded_extensions'):
                import re as _re
                _ext_pattern = _re.compile(r'^\.[a-zA-Z0-9]{1,10}$')
                for ext in self.config.file_monitoring.excluded_extensions:
                    if isinstance(ext, str) and _ext_pattern.match(ext):
                        filesystem_monitor.EXCLUDED_EXTENSIONS.add(ext)
                    else:
                        logger.warning(f"Rejected invalid excluded extension from config: {ext!r}")
            self.monitors.append(filesystem_monitor)
            logger.info("Filesystem monitor initialized")

        # Registry monitor (Windows only)
        if self.config.registry_monitoring.enabled:
            registry_monitor = RegistryMonitor(self.event_bus)
            self.monitors.append(registry_monitor)
            logger.info("Registry monitor initialized")

        # Inject system components into routes
        system.set_system_components(self.event_bus, self.monitors, self.rule_engine)
        websocket.set_event_bus(self.event_bus)

    async def start(self):
        """Start all components."""
        logger.info("Starting CHIPS service...")

        # Start event bus
        await self.event_bus.start()

        # Start activity logger (must start before monitors to capture all events)
        await self.activity_logger.start()

        # Start rule engine
        await self.rule_engine.start()

        # Start all monitors
        for monitor in self.monitors:
            await monitor.start()

        # Apply persisted settings (excluded_processes, max_alerts_per_hour)
        # — watched_paths and intervals come from hips_config.yaml at startup
        try:
            from hips_service.api.routes.settings import load_settings
            saved = load_settings()
            for monitor in self.monitors:
                if hasattr(monitor, 'update_excluded_processes'):
                    monitor.update_excluded_processes(
                        saved.get('monitoring', {}).get('excluded_processes', [])
                    )
            if self.rule_engine:
                self.rule_engine.update_max_alerts_per_hour(
                    saved.get('alerts', {}).get('max_per_hour', 100)
                )
        except Exception as e:
            logger.warning(f"Could not apply saved settings at startup: {e}")

        # Start auto-cleanup background task
        self._cleanup_task = asyncio.create_task(self._auto_cleanup_loop())

        logger.info("All components started successfully")
        logger.info(f"API server starting on {self.config.api.host}:{self.config.api.port}")

    async def _auto_cleanup_loop(self):
        """Daily database cleanup when auto_cleanup is enabled in settings."""
        import sqlite3
        while True:
            await asyncio.sleep(86400)  # run once every 24 hours
            try:
                from hips_service.api.routes.settings import load_settings
                saved = load_settings()
                if not saved.get('database', {}).get('auto_cleanup', True):
                    continue
                retention_days = max(1, int(saved.get('database', {}).get('retention_days', 90)))
                db_path = os.path.abspath(self.config.database.path)
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                deleted = 0
                for table in ["alerts", "activity_logs", "blocked_actions"]:
                    try:
                        result = cur.execute(
                            f"DELETE FROM {table} WHERE timestamp < datetime('now', ? || ' days')",  # noqa: S608
                            (f"-{retention_days}",)
                        )
                        deleted += result.rowcount
                    except sqlite3.Error as e:
                        logger.error(f"Auto-cleanup error on table {table!r}: {e}")
                conn.commit()
                conn.close()
                logger.info(f"Auto-cleanup complete: {deleted} records deleted (>{retention_days} days)")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Auto-cleanup failed: {e}", exc_info=True)

    async def stop(self):
        """Stop all components."""
        logger.info("Stopping CHIPS service...")

        # Stop cleanup scheduler
        if self._cleanup_task:
            self._cleanup_task.cancel()

        # Stop monitors
        for monitor in self.monitors:
            await monitor.stop()

        # Stop rule engine
        await self.rule_engine.stop()

        # Stop activity logger
        if self.activity_logger:
            await self.activity_logger.stop()

        # Stop event bus
        await self.event_bus.stop()

        logger.info("CHIPS service stopped")


# Global service instance
_service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — handles startup and graceful shutdown."""
    global _service
    _service = CHIPSService()
    await _service.initialize()
    await _service.start()
    yield
    if _service:
        await _service.stop()


# Application instance — created with the lifespan context manager
app = create_app(lifespan=lifespan)


def main():
    """Main entry point."""
    config = get_config()

    # Run FastAPI server
    uvicorn.run(
        "hips_service.main:app",
        host=config.api.host,
        port=config.api.port,
        reload=config.api.reload,
        log_level=config.api.log_level
    )


if __name__ == "__main__":
    main()

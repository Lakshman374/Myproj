"""System API routes."""

import logging
import os
import sqlite3
import tempfile
import time
from datetime import datetime, timedelta
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from hips_service.core.config import get_config
from hips_service.core.platform_detector import PlatformDetector

router = APIRouter()
logger = logging.getLogger(__name__)

_start_time = time.time()
_last_cleanup: str | None = None

# Will be injected by main
_event_bus = None
_monitors = []
_rule_engine = None


def set_system_components(event_bus, monitors, rule_engine=None):
    """Set system components."""
    global _event_bus, _monitors, _rule_engine
    _event_bus = event_bus
    _monitors = monitors
    _rule_engine = rule_engine


def apply_monitoring_settings(process_interval: int, filesystem_interval: int,
                               network_interval: int, watched_paths: list,
                               excluded_processes: list = None,
                               max_alerts_per_hour: int = None) -> list:
    """Apply monitoring settings to the running monitors at runtime.

    Args:
        process_interval: New process polling interval in seconds
        filesystem_interval: New filesystem check interval in seconds (informational)
        network_interval: New network check interval in seconds (informational)
        watched_paths: New list of filesystem paths to watch
        excluded_processes: Process names to suppress from event emission
        max_alerts_per_hour: Per-rule alert rate cap

    Returns:
        List of applied change descriptions
    """
    import asyncio
    from hips_service.monitors.process_monitor import ProcessMonitor
    from hips_service.monitors.filesystem_monitor import FilesystemMonitor

    applied = []

    for monitor in _monitors:
        if isinstance(monitor, ProcessMonitor):
            monitor.update_interval(process_interval)
            applied.append(f"ProcessMonitor interval → {process_interval}s")
            if excluded_processes is not None:
                monitor.update_excluded_processes(excluded_processes)
                applied.append(f"ProcessMonitor excluded → {excluded_processes}")

        elif isinstance(monitor, FilesystemMonitor):
            if watched_paths:
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(monitor.update_watched_paths(watched_paths))
                    applied.append(f"FilesystemMonitor paths → {watched_paths}")
                except RuntimeError:
                    pass

    if _rule_engine is not None and max_alerts_per_hour is not None:
        _rule_engine.update_max_alerts_per_hour(max_alerts_per_hour)
        applied.append(f"RuleEngine max_alerts_per_hour → {max_alerts_per_hour}")

    if not applied:
        logger.warning("apply_monitoring_settings called but no monitors found")

    logger.info(f"Settings applied: {applied}")
    return applied


class SystemStatus(BaseModel):
    """System status response."""
    platform: str
    running: bool
    monitors: list
    event_bus_stats: dict


class PlatformInfo(BaseModel):
    """Platform information."""
    platform: str
    supported: bool


@router.get("/status")
async def get_system_status():
    """Get system status."""
    uptime_seconds = int(time.time() - _start_time)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{hours}h {minutes}m {seconds}s"

    return {
        "status": "Running",
        "uptime": uptime_str,
        "version": "1.0.0",
        "platform": PlatformDetector.get_platform_name(),
        "running": True,
    }


@router.get("/platform", response_model=PlatformInfo)
async def get_platform_info():
    """Get platform information."""
    return PlatformInfo(
        platform=PlatformDetector.get_platform_name(),
        supported=PlatformDetector.is_supported()
    )


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@router.get("/database/info")
async def get_database_info():
    """Get database file info."""
    db_path = os.path.abspath(get_config().database.path)
    size_str = "N/A"
    records_str = "N/A"
    if os.path.exists(db_path):
        size_bytes = os.path.getsize(db_path)
        if size_bytes < 1024 * 1024:
            size_str = f"{size_bytes / 1024:.1f} KB"
        else:
            size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            _KNOWN_TABLES = ["alerts", "activity_logs", "blocked_actions"]
            total = 0
            for table in _KNOWN_TABLES:
                try:
                    count = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608 — whitelisted
                    total += count
                except sqlite3.Error as e:
                    logger.warning(f"Could not count rows in table {table!r}: {e}")
            conn.close()
            records_str = str(total)
        except sqlite3.Error as e:
            logger.error(f"Error reading database info: {e}", exc_info=True)
    return {
        "size": size_str,
        "records": records_str,
        "last_cleanup": _last_cleanup or "Never",
    }


@router.post("/database/cleanup")
async def cleanup_database():
    """Delete old records from the database."""
    global _last_cleanup
    from hips_service.api.routes.settings import load_settings
    from hips_service.database.models import Alert, ActivityLog, BlockedAction, get_db

    retention_days = max(1, int(load_settings().get("database", {}).get("retention_days", 90)))
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    deleted = 0

    try:
        with get_db() as db:
            for model in [Alert, ActivityLog, BlockedAction]:
                deleted += db.query(model).filter(model.timestamp < cutoff).delete(synchronize_session=False)
            db.commit()
        logger.info(f"Database cleanup complete: {deleted} records deleted (cutoff: {cutoff})")
    except Exception as e:
        logger.error(f"Database cleanup failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database cleanup failed: {e}")

    _last_cleanup = datetime.now().strftime("%Y-%m-%d %H:%M")
    return {"deleted": deleted, "status": "ok"}


@router.get("/database/backup")
async def backup_database(background_tasks: BackgroundTasks):
    """Download a consistent snapshot of the database."""
    db_path = os.path.abspath(get_config().database.path)
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="Database file not found")

    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        tmp.close()
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(tmp.name)
        src.backup(dst)
        dst.close()
        src.close()
    except Exception as e:
        logger.error(f"Database backup failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database backup failed: {e}")

    background_tasks.add_task(os.unlink, tmp.name)
    return FileResponse(
        path=tmp.name,
        media_type="application/octet-stream",
        filename="hips_data.db",
    )

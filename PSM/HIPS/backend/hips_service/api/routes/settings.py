"""Settings API routes."""

import json
import logging
import os
import sys
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional

logger = logging.getLogger(__name__)

router = APIRouter()

# Path to persist settings
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "../../../../hips_settings.json")

_DEFAULT_WATCHED_PATHS = (
    ["C:\\Users"]
    if sys.platform == "win32" else
    ["/etc", "/tmp", "/var/tmp", "/home", "/root", "/var/www", "/opt", "/usr/local/bin"]
)

_DEFAULT_EXCLUDED_PROCESSES = (
    ["svchost.exe", "lsass.exe", "csrss.exe", "wininit.exe", "services.exe"]
    if sys.platform == "win32" else
    ["systemd", "kthreadd", "ksoftirqd", "kworker"]
)

# Default settings — must match hips_config.yaml values
DEFAULT_SETTINGS = {
    "monitoring": {
        "process_interval": 3,
        "filesystem_interval": 5,
        "network_interval": 5,
        "watched_paths": _DEFAULT_WATCHED_PATHS,
        "excluded_processes": _DEFAULT_EXCLUDED_PROCESSES,
    },
    "alerts": {
        "max_per_hour": 100,
        "retention_days": 30,
        "email_notifications": False,
        "webhook_url": None
    },
    "database": {
        "retention_days": 90,
        "auto_cleanup": True,
        "max_size_mb": 500
    },
    "logging": {
        "level": "INFO",
        "max_file_size_mb": 10,
        "backup_count": 5
    }
}


def load_settings() -> dict:
    """Load settings from file, falling back to defaults."""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load settings file: {e}")
    return DEFAULT_SETTINGS.copy()


def save_settings(settings: dict):
    """Persist settings to file."""
    try:
        with open(SETTINGS_FILE, "w", encoding='utf-8') as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {e}")


# --- Pydantic models ---

class MonitoringSettings(BaseModel):
    process_interval: int = 3
    filesystem_interval: int = 5
    network_interval: int = 5
    watched_paths: List[str] = []
    excluded_processes: List[str] = []


class AlertSettings(BaseModel):
    max_per_hour: int = 100
    retention_days: int = 30
    email_notifications: bool = False
    webhook_url: Optional[str] = None


class DatabaseSettings(BaseModel):
    retention_days: int = Field(default=90, ge=1, le=3650)
    auto_cleanup: bool = True
    max_size_mb: int = Field(default=500, ge=1)


class LoggingSettings(BaseModel):
    level: str = "INFO"
    max_file_size_mb: int = 10
    backup_count: int = 5


class SystemSettings(BaseModel):
    monitoring: MonitoringSettings
    alerts: AlertSettings
    database: DatabaseSettings
    logging: LoggingSettings


# --- Routes ---

import yaml

CONFIG_YAML_FILE = os.path.join(os.path.dirname(__file__), "../../../config/hips_config.yaml")


def _validate_watched_paths(paths: List[str]):
    """Reject paths that are not absolute or contain traversal components."""
    for path in paths:
        if not isinstance(path, str) or len(path) > 512:
            raise HTTPException(status_code=422, detail=f"Invalid path: {path!r}")
        if not os.path.isabs(path):
            raise HTTPException(
                status_code=422,
                detail=f"Watched path must be absolute: {path!r}",
            )
        # Normalize and confirm no traversal components remain
        normalized = os.path.normpath(path)
        if ".." in normalized.split(os.sep):
            raise HTTPException(
                status_code=422,
                detail=f"Path traversal not allowed: {path!r}",
            )


def _patch_config_yaml(monitoring: "MonitoringSettings"):
    """Persist interval and path changes to hips_config.yaml so they survive restarts."""
    try:
        with open(CONFIG_YAML_FILE, "r", encoding='utf-8') as f:
            config = yaml.safe_load(f)

        config["process_monitoring"]["interval_seconds"] = monitoring.process_interval
        config["file_monitoring"]["interval_seconds"] = monitoring.filesystem_interval
        config["network_monitoring"]["interval_seconds"] = monitoring.network_interval
        if monitoring.watched_paths:
            config["file_monitoring"]["watched_paths"] = monitoring.watched_paths

        with open(CONFIG_YAML_FILE, "w", encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

        logger.info("hips_config.yaml updated with new monitoring settings")
    except Exception as e:
        logger.warning(f"Could not update hips_config.yaml: {e}")


@router.get("", response_model=SystemSettings)
async def get_settings():
    """Get current system settings."""
    data = load_settings()
    return SystemSettings(**data)


@router.put("")
async def update_settings(updated: SystemSettings):
    """Update system settings, apply to live monitors, and persist to hips_config.yaml."""
    from hips_service.api.routes.system import apply_monitoring_settings

    # Validate paths before touching any files
    _validate_watched_paths(updated.monitoring.watched_paths)

    # 1. Save to hips_settings.json
    data = updated.model_dump()
    save_settings(data)

    # 2. Apply to running monitors immediately
    applied = apply_monitoring_settings(
        process_interval=updated.monitoring.process_interval,
        filesystem_interval=updated.monitoring.filesystem_interval,
        network_interval=updated.monitoring.network_interval,
        watched_paths=updated.monitoring.watched_paths,
        excluded_processes=updated.monitoring.excluded_processes,
        max_alerts_per_hour=updated.alerts.max_per_hour,
    )

    # 3. Persist to hips_config.yaml so changes survive restarts
    _patch_config_yaml(updated.monitoring)

    # 4. Apply log level immediately to the running hips_service logger tree
    import logging as _logging
    level = updated.logging.level.upper()
    if level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        _logging.getLogger("hips_service").setLevel(level)
        logger.info(f"Log level updated to {level}")

    return {**data, "applied": applied}


@router.post("/reset", response_model=SystemSettings)
async def reset_settings():
    """Reset settings to defaults."""
    save_settings(DEFAULT_SETTINGS.copy())
    return SystemSettings(**DEFAULT_SETTINGS)

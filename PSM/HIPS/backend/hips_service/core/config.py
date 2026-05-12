"""Configuration management for HIPS."""

import os
from pathlib import Path
from typing import List, Dict, Any
import yaml
from pydantic import BaseModel, Field


class MonitoringConfig(BaseModel):
    """Monitoring configuration."""
    enabled: bool = True
    interval_seconds: int = Field(default=5, ge=1, le=60)
    max_events_per_batch: int = Field(default=100, ge=10, le=1000)


class ProcessMonitoringConfig(MonitoringConfig):
    """Process monitoring configuration."""
    track_children: bool = True
    monitor_privilege_escalation: bool = True


class FileMonitoringConfig(MonitoringConfig):
    """File monitoring configuration."""
    watched_paths: List[str] = Field(default_factory=list)
    excluded_extensions: List[str] = Field(default_factory=lambda: ['.tmp', '.swp'])
    detect_rapid_changes: bool = True
    rapid_change_threshold: int = Field(default=50, ge=10)
    rapid_change_window_seconds: int = Field(default=60, ge=10)


class NetworkMonitoringConfig(MonitoringConfig):
    """Network monitoring configuration."""
    monitor_outbound: bool = True
    monitor_inbound: bool = False
    suspicious_ports: List[int] = Field(default_factory=lambda: [4444, 5555, 6666, 7777, 8888, 9999])


class RegistryMonitoringConfig(BaseModel):
    """Windows registry monitoring configuration."""
    enabled: bool = True


class DatabaseConfig(BaseModel):
    """Database configuration."""
    path: str = "./hips_data.db"
    echo: bool = False
    pool_size: int = 5


class APIConfig(BaseModel):
    """API server configuration."""
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = False
    log_level: str = "info"


class Config(BaseModel):
    """Main HIPS configuration."""
    process_monitoring: ProcessMonitoringConfig = Field(default_factory=ProcessMonitoringConfig)
    file_monitoring: FileMonitoringConfig = Field(default_factory=FileMonitoringConfig)
    network_monitoring: NetworkMonitoringConfig = Field(default_factory=NetworkMonitoringConfig)
    registry_monitoring: RegistryMonitoringConfig = Field(default_factory=RegistryMonitoringConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    rules_directory: str = "./backend/rules"
    log_retention_days: int = Field(default=30, ge=1)

    @classmethod
    def load_from_file(cls, config_path: str) -> "Config":
        """Load configuration from YAML file.

        Args:
            config_path: Path to configuration file

        Returns:
            Config instance
        """
        path = Path(config_path)
        if not path.exists():
            return cls()

        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        return cls(**data) if data else cls()

    def save_to_file(self, config_path: str):
        """Save configuration to YAML file.

        Args:
            config_path: Path to save configuration
        """
        path = Path(config_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False)


# Global configuration instance
_config: Config = None


def get_config() -> Config:
    """Get global configuration instance.

    Returns:
        Config instance
    """
    global _config
    if _config is None:
        config_path = os.getenv('HIPS_CONFIG', './config/hips_config.yaml')
        _config = Config.load_from_file(config_path)
    return _config


def set_config(config: Config):
    """Set global configuration instance.

    Args:
        config: Config instance to set
    """
    global _config
    _config = config

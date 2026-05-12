"""Monitoring API routes for real-time system information."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
import psutil
from datetime import datetime

from hips_service.database.models import ActivityLog, get_session

router = APIRouter()


class SystemInfo(BaseModel):
    """System information."""
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_connections: int
    process_count: int
    uptime: float


class ProcessInfo(BaseModel):
    """Process information."""
    pid: int
    name: str
    username: Optional[str] = None
    cpu_percent: float
    memory_percent: float
    status: str
    create_time: float


class FilesystemActivity(BaseModel):
    """Recent filesystem activity."""
    path: str
    operation: str
    timestamp: datetime
    process_name: Optional[str] = None
    process_pid: Optional[int] = None


class NetworkConnection(BaseModel):
    """Network connection information."""
    local_address: str
    local_port: int
    remote_address: str
    remote_port: int
    status: str
    pid: Optional[int] = None
    process_name: Optional[str] = None


@router.get("/system", response_model=SystemInfo)
async def get_system_info():
    """Get real-time system information."""
    try:
        # Get system metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        _partitions = psutil.disk_partitions()
        disk = psutil.disk_usage(_partitions[0].mountpoint) if _partitions else psutil.disk_usage('.')
        network_connections = len(psutil.net_connections())
        process_count = len(psutil.pids())

        # Calculate uptime
        boot_time = psutil.boot_time()
        uptime = datetime.now().timestamp() - boot_time

        return SystemInfo(
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            disk_percent=disk.percent,
            network_connections=network_connections,
            process_count=process_count,
            uptime=uptime
        )
    except Exception as e:
        # Return default values if error
        return SystemInfo(
            cpu_percent=0.0,
            memory_percent=0.0,
            disk_percent=0.0,
            network_connections=0,
            process_count=0,
            uptime=0.0
        )


@router.get("/processes", response_model=List[ProcessInfo])
async def get_processes(limit: int = 10, sort_by: str = "cpu"):
    """Get list of top processes by CPU or memory usage.

    Args:
        limit: Maximum number of processes to return
        sort_by: Sort by 'cpu' or 'memory'
    """
    processes = []

    try:
        for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent', 'status', 'create_time']):
            try:
                info = proc.info
                processes.append(ProcessInfo(
                    pid=info['pid'],
                    name=info['name'] or 'unknown',
                    username=info.get('username'),
                    cpu_percent=info.get('cpu_percent') or 0.0,
                    memory_percent=info.get('memory_percent') or 0.0,
                    status=info.get('status') or 'unknown',
                    create_time=info.get('create_time') or 0.0
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Sort processes
        if sort_by == "memory":
            processes.sort(key=lambda p: p.memory_percent, reverse=True)
        else:
            processes.sort(key=lambda p: p.cpu_percent, reverse=True)

        return processes[:limit]

    except Exception as e:
        return []


@router.get("/filesystem", response_model=List[FilesystemActivity])
async def get_filesystem_activity(
    limit: int = 50,
    db: Session = Depends(get_session)
):
    """Get recent filesystem activity from the activity_logs database table."""
    logs = (
        db.query(ActivityLog)
        .filter(ActivityLog.event_type.like("file_%"))
        .order_by(ActivityLog.timestamp.desc())
        .limit(limit)
        .all()
    )

    return [
        FilesystemActivity(
            path=log.file_path or "unknown",
            operation=log.file_operation or log.event_type.replace("file_", ""),
            timestamp=log.timestamp,
            process_name=log.process_name,
            process_pid=log.process_pid,
        )
        for log in logs
    ]


@router.get("/network", response_model=List[NetworkConnection])
async def get_network_connections(limit: int = 20):
    """Get active network connections."""
    connections = []

    try:
        for conn in psutil.net_connections(kind='inet'):
            try:
                # Get process info if available
                process_name = None
                if conn.pid:
                    try:
                        proc = psutil.Process(conn.pid)
                        process_name = proc.name()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

                connections.append(NetworkConnection(
                    local_address=conn.laddr.ip if conn.laddr else "",
                    local_port=conn.laddr.port if conn.laddr else 0,
                    remote_address=conn.raddr.ip if conn.raddr else "",
                    remote_port=conn.raddr.port if conn.raddr else 0,
                    status=conn.status,
                    pid=conn.pid,
                    process_name=process_name
                ))

                if len(connections) >= limit:
                    break

            except Exception:
                continue

        return connections

    except Exception as e:
        return []


@router.get("/disk-usage")
async def get_disk_usage():
    """Get disk usage for all partitions."""
    partitions = []

    try:
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                partitions.append({
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "fstype": partition.fstype,
                    "total": usage.total,
                    "used": usage.used,
                    "free": usage.free,
                    "percent": usage.percent
                })
            except PermissionError:
                continue

        return partitions

    except Exception as e:
        return []

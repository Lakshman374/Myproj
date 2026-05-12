"""Activity logs API routes."""

import csv
import io
import json
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from hips_service.database.models import ActivityLog, get_session
from pydantic import BaseModel

router = APIRouter()


class LogResponse(BaseModel):
    """Activity log response model."""
    id: int
    timestamp: datetime
    event_type: str
    platform: str
    severity: str
    process_name: Optional[str] = None
    process_pid: Optional[int] = None
    process_path: Optional[str] = None
    file_path: Optional[str] = None
    file_operation: Optional[str] = None
    dst_ip: Optional[str] = None
    dst_port: Optional[int] = None
    registry_key: Optional[str] = None
    registry_operation: Optional[str] = None
    registry_value: Optional[str] = None

    class Config:
        from_attributes = True


class LogsListResponse(BaseModel):
    """Logs list response."""
    total: int
    logs: List[LogResponse]


@router.get("/export")
async def export_logs(
    format: str = Query("csv", regex="^(csv|json)$"),
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    process_name: Optional[str] = None,
    limit: int = Query(1000, ge=1, le=10000),
    db: Session = Depends(get_session)
):
    """Export activity logs as CSV or JSON."""
    query = db.query(ActivityLog)

    if event_type:
        query = query.filter(ActivityLog.event_type == event_type)
    if severity:
        query = query.filter(ActivityLog.severity == severity)
    if process_name:
        escaped = process_name.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        query = query.filter(ActivityLog.process_name.like(f"%{escaped}%", escape='\\'))

    logs = query.order_by(ActivityLog.timestamp.desc()).limit(limit).all()

    fields = ["id", "timestamp", "event_type", "platform", "severity",
              "process_name", "process_pid", "process_path", "file_path",
              "file_operation", "dst_ip", "dst_port",
              "registry_key", "registry_operation", "registry_value"]

    if format == "json":
        data = [
            {f: (getattr(log, f).isoformat() if isinstance(getattr(log, f), datetime) else getattr(log, f))
             for f in fields}
            for log in logs
        ]
        content = json.dumps(data, indent=2)
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=activity-logs.json"}
        )

    # CSV
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for log in logs:
        writer.writerow({
            f: (getattr(log, f).isoformat() if isinstance(getattr(log, f), datetime) else getattr(log, f))
            for f in fields
        })
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=activity-logs.csv"}
    )


@router.get("", response_model=LogsListResponse)
async def get_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    process_name: Optional[str] = None,
    db: Session = Depends(get_session)
):
    """Get activity logs with filtering and pagination."""
    query = db.query(ActivityLog)

    # Apply filters
    if event_type:
        query = query.filter(ActivityLog.event_type == event_type)
    if severity:
        query = query.filter(ActivityLog.severity == severity)
    if process_name:
        escaped = process_name.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        query = query.filter(ActivityLog.process_name.like(f"%{escaped}%", escape='\\'))

    # Get total count
    total = query.count()

    # Get logs with pagination
    logs = query.order_by(ActivityLog.timestamp.desc()).offset(skip).limit(limit).all()

    return LogsListResponse(total=total, logs=logs)

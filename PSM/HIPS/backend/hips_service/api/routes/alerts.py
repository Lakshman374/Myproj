"""Alerts API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from hips_service.database.models import Alert, BlockedAction, get_session
from hips_service.utils.time import get_local_time
from pydantic import BaseModel

router = APIRouter()


class AlertResponse(BaseModel):
    """Alert response model."""
    id: int
    timestamp: datetime
    rule_id: str
    rule_name: str
    severity: str
    category: str
    message: str
    status: str
    platform: str
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AlertsListResponse(BaseModel):
    """Alerts list response."""
    total: int
    alerts: List[AlertResponse]


@router.get("", response_model=AlertsListResponse)
async def get_alerts(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    severity: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_session)
):
    """Get list of alerts with filtering and pagination."""
    query = db.query(Alert)

    # Apply filters
    if severity:
        query = query.filter(Alert.severity == severity)
    if status:
        query = query.filter(Alert.status == status)
    if category:
        query = query.filter(Alert.category == category)

    # Get total count
    total = query.count()

    # Get alerts with pagination
    alerts = query.order_by(Alert.timestamp.desc()).offset(skip).limit(limit).all()

    return AlertsListResponse(total=total, alerts=alerts)


class BlockedActionResponse(BaseModel):
    """Blocked action response model."""
    id: int
    timestamp: datetime
    rule_id: Optional[str] = None
    action_type: str
    target: Optional[str] = None
    reason: Optional[str] = None
    platform: Optional[str] = None

    class Config:
        from_attributes = True


class BlockedActionsListResponse(BaseModel):
    """Blocked actions list response."""
    total: int
    blocked_actions: List[BlockedActionResponse]


@router.get("/blocked", response_model=BlockedActionsListResponse)
async def get_blocked_actions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    db: Session = Depends(get_session)
):
    """Get list of blocked actions."""
    total = db.query(BlockedAction).count()
    items = db.query(BlockedAction).order_by(BlockedAction.timestamp.desc()).offset(skip).limit(limit).all()
    return BlockedActionsListResponse(total=total, blocked_actions=items)


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(alert_id: int, db: Session = Depends(get_session)):
    """Get specific alert by ID."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    return alert


@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(alert_id: int, db: Session = Depends(get_session)) -> AlertResponse:
    """Acknowledge an alert."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = "acknowledged"
    alert.acknowledged_at = get_local_time()
    db.commit()
    db.refresh(alert)

    return alert


@router.post("/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert(alert_id: int, db: Session = Depends(get_session)) -> AlertResponse:
    """Resolve an alert."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = "resolved"
    alert.resolved_at = get_local_time()
    db.commit()
    db.refresh(alert)

    return alert


@router.delete("/{alert_id}")
async def delete_alert(alert_id: int, db: Session = Depends(get_session)):
    """Delete an alert."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    db.delete(alert)
    db.commit()

    return {"message": "Alert deleted", "alert_id": alert_id}


class BulkActionRequest(BaseModel):
    """Request body for bulk alert operations."""
    ids: List[int]


@router.post("/bulk-acknowledge")
async def bulk_acknowledge_alerts(
    request: BulkActionRequest,
    db: Session = Depends(get_session)
):
    """Acknowledge multiple alerts at once."""
    now = get_local_time()
    result = (
        db.query(Alert)
        .filter(Alert.id.in_(request.ids), Alert.status != "acknowledged")
        .update({"status": "acknowledged", "acknowledged_at": now}, synchronize_session=False)
    )
    db.commit()
    return {"message": f"Acknowledged {result} alerts", "updated": result}


@router.post("/bulk-resolve")
async def bulk_resolve_alerts(
    request: BulkActionRequest,
    db: Session = Depends(get_session)
):
    """Resolve multiple alerts at once."""
    now = get_local_time()
    result = (
        db.query(Alert)
        .filter(Alert.id.in_(request.ids), Alert.status != "resolved")
        .update({"status": "resolved", "resolved_at": now}, synchronize_session=False)
    )
    db.commit()
    return {"message": f"Resolved {result} alerts", "updated": result}


@router.post("/bulk-delete")
async def bulk_delete_alerts(
    request: BulkActionRequest,
    db: Session = Depends(get_session)
):
    """Delete multiple alerts at once."""
    result = (
        db.query(Alert)
        .filter(Alert.id.in_(request.ids))
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"message": f"Deleted {result} alerts", "deleted": result}

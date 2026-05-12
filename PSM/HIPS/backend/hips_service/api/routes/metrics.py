"""Metrics API routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import Dict, List
import logging

from hips_service.database.models import Alert, ActivityLog, BlockedAction, get_session
from hips_service.utils.time import get_local_time
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class DashboardMetrics(BaseModel):
    """Dashboard metrics response."""
    total_alerts: int
    new_alerts: int
    critical_alerts: int
    blocked_actions: int
    events_last_hour: int
    events_last_24h: int


class TimelineData(BaseModel):
    """Timeline data point."""
    timestamp: str
    count: int


class CategoryCount(BaseModel):
    """Category count."""
    category: str
    count: int


@router.get("/dashboard", response_model=DashboardMetrics)
async def get_dashboard_metrics(db: Session = Depends(get_session)):
    """Get dashboard metrics."""
    # Total alerts
    total_alerts = db.query(Alert).count()

    # New alerts
    new_alerts = db.query(Alert).filter(Alert.status == 'new').count()

    # Critical alerts
    critical_alerts = db.query(Alert).filter(Alert.severity == 'critical').count()

    # Blocked actions
    blocked_actions = db.query(BlockedAction).count()

    # Events in last hour
    one_hour_ago = get_local_time() - timedelta(hours=1)
    events_last_hour = db.query(ActivityLog).filter(ActivityLog.timestamp >= one_hour_ago).count()

    # Events in last 24 hours
    one_day_ago = get_local_time() - timedelta(days=1)
    events_last_24h = db.query(ActivityLog).filter(ActivityLog.timestamp >= one_day_ago).count()

    return DashboardMetrics(
        total_alerts=total_alerts,
        new_alerts=new_alerts,
        critical_alerts=critical_alerts,
        blocked_actions=blocked_actions,
        events_last_hour=events_last_hour,
        events_last_24h=events_last_24h
    )


@router.get("/timeline")
async def get_timeline(hours: int = 24, db: Session = Depends(get_session)):
    """Get timeline data for activity graph."""
    start_time = get_local_time() - timedelta(hours=hours)

    try:
        # Query events grouped by hour (SQLite-specific strftime)
        results = db.query(
            func.strftime('%Y-%m-%d %H:00:00', ActivityLog.timestamp).label('hour'),
            func.count(ActivityLog.id).label('count')
        ).filter(
            ActivityLog.timestamp >= start_time
        ).group_by('hour').order_by('hour').all()

        return [
            TimelineData(timestamp=row.hour, count=row.count)
            for row in results
        ]
    except Exception as e:
        logger.error(f"Error fetching timeline data: {e}", exc_info=True)
        return []


@router.get("/categories")
async def get_category_distribution(db: Session = Depends(get_session)):
    """Get alert distribution by category."""
    results = db.query(
        Alert.category,
        func.count(Alert.id).label('count')
    ).group_by(Alert.category).all()

    categories = [
        CategoryCount(category=row.category, count=row.count)
        for row in results
    ]

    return categories

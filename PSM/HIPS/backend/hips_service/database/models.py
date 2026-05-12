"""Database models for HIPS."""

from contextlib import contextmanager
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, Text, Float, Index, create_engine
)
from sqlalchemy.orm import declarative_base, sessionmaker

from hips_service.utils.time import get_local_time

Base = declarative_base()


class Alert(Base):
    """Alert model for storing triggered alerts."""

    __tablename__ = 'alerts'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=get_local_time, index=True, nullable=False)
    rule_id = Column(String(100), index=True)
    rule_name = Column(String(200))
    severity = Column(String(20), index=True)  # low, medium, high, critical
    category = Column(String(50), index=True)
    message = Column(Text)
    event_data = Column(Text)  # JSON serialized
    status = Column(String(20), default='new', index=True)  # new, acknowledged, resolved
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    platform = Column(String(20))

    __table_args__ = (
        Index('idx_timestamp_severity', 'timestamp', 'severity'),
    )

    def __repr__(self):
        return f"<Alert(id={self.id}, rule_name='{self.rule_name}', severity='{self.severity}')>"


class ActivityLog(Base):
    """Activity log model for storing monitored events."""

    __tablename__ = 'activity_logs'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=get_local_time, index=True, nullable=False)
    event_type = Column(String(50), index=True, nullable=False)  # process_create, file_modify, etc.
    platform = Column(String(20))
    severity = Column(String(20), index=True)

    # Process details
    process_name = Column(String(255), index=True)
    process_pid = Column(Integer)
    process_path = Column(Text)
    process_cmdline = Column(Text)
    parent_pid = Column(Integer)
    parent_name = Column(String(255))

    # File details
    file_path = Column(Text)
    file_operation = Column(String(50))
    file_hash = Column(String(64))  # SHA-256

    # Network details
    src_ip = Column(String(45))
    src_port = Column(Integer)
    dst_ip = Column(String(45), index=True)
    dst_port = Column(Integer, index=True)
    protocol = Column(String(10))

    # Registry details (Windows)
    registry_key = Column(Text)
    registry_operation = Column(String(50))
    registry_value = Column(Text)

    # Additional data
    user = Column(String(100))
    extra_data = Column(Text)  # JSON for additional fields

    __table_args__ = (
        Index('idx_timestamp_event_type', 'timestamp', 'event_type'),
        Index('idx_process_name_timestamp', 'process_name', 'timestamp'),
    )

    def __repr__(self):
        return f"<ActivityLog(id={self.id}, event_type='{self.event_type}', timestamp={self.timestamp})>"


class BlockedAction(Base):
    """Blocked action model for storing blocked processes/connections."""

    __tablename__ = 'blocked_actions'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=get_local_time, index=True, nullable=False)
    rule_id = Column(String(100))
    action_type = Column(String(50))  # process_blocked, connection_blocked
    target = Column(Text)
    reason = Column(Text)
    event_data = Column(Text)  # JSON
    platform = Column(String(20))

    def __repr__(self):
        return f"<BlockedAction(id={self.id}, action_type='{self.action_type}', timestamp={self.timestamp})>"


class RuleExecution(Base):
    """Rule execution model for tracking rule performance."""

    __tablename__ = 'rule_executions'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=get_local_time, index=True, nullable=False)
    rule_id = Column(String(100), index=True)
    matched = Column(Boolean, index=True)
    execution_time_ms = Column(Float)
    event_type = Column(String(50))

    def __repr__(self):
        return f"<RuleExecution(rule_id='{self.rule_id}', matched={self.matched})>"


class SystemMetrics(Base):
    """System metrics model for monitoring performance."""

    __tablename__ = 'system_metrics'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=get_local_time, index=True, nullable=False)
    metric_name = Column(String(100), index=True)
    metric_value = Column(Float)
    platform = Column(String(20))

    # Performance metrics
    cpu_percent = Column(Float)
    memory_percent = Column(Float)
    events_processed = Column(Integer)
    events_queued = Column(Integer)

    def __repr__(self):
        return f"<SystemMetrics(metric_name='{self.metric_name}', value={self.metric_value})>"


# Database engine and session factory
_engine = None
_SessionLocal = None


def init_db(database_url: str = "sqlite:///./hips_data.db", echo: bool = False):
    """Initialize database connection and create tables.

    Args:
        database_url: Database connection string
        echo: Whether to echo SQL statements
    """
    global _engine, _SessionLocal

    _engine = create_engine(
        database_url,
        echo=echo,
        connect_args={"check_same_thread": False} if "sqlite" in database_url else {}
    )

    # Create all tables
    Base.metadata.create_all(bind=_engine)

    # Create session factory
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def get_session():
    """Get database session.

    Yields:
        Database session
    """
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db():
    """Context manager for safely acquiring and releasing a database session.

    Automatically rolls back on exception and always closes the session.

    Yields:
        Active database session

    Raises:
        RuntimeError: If database has not been initialised via init_db()
    """
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    db = _SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_engine():
    """Get database engine.

    Returns:
        SQLAlchemy engine
    """
    return _engine

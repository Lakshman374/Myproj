"""Time utilities for HIPS."""

from datetime import datetime, timedelta, timezone

def get_local_time() -> datetime:
    """Get the current time in Malaysia timezone (UTC+8).
    
    This is used to ensure consistency because datetime.now() 
    can return UTC on some systems.
    
    Returns:
        Current datetime in UTC+8
    """
    # Create fixed offset for Malaysia (UTC+8)
    malaysia_tz = timezone(timedelta(hours=8))
    # Return time in that timezone, but stripped of tzinfo for SQLAlchemy compatibility
    return datetime.now(malaysia_tz).replace(tzinfo=None)

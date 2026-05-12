"""Base monitor interface for all monitoring modules."""

from abc import ABC, abstractmethod
from typing import List, Optional
from hips_service.core.event_bus import EventBus, MonitorEvent
import logging

logger = logging.getLogger(__name__)


class BaseMonitor(ABC):
    """Abstract base class for all monitors."""

    def __init__(self, event_bus: EventBus, name: str):
        """Initialize base monitor.

        Args:
            event_bus: Event bus for publishing events
            name: Name of the monitor
        """
        self.event_bus = event_bus
        self.name = name
        self.running = False
        self._monitor_task = None

    @abstractmethod
    async def start(self):
        """Start monitoring.

        This method should begin the monitoring loop and publish events
        to the event bus.
        """
        pass

    @abstractmethod
    async def stop(self):
        """Stop monitoring.

        This method should clean up resources and stop the monitoring loop.
        """
        pass

    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """Get list of monitoring capabilities.

        Returns:
            List of capability names
        """
        pass

    async def publish_event(self, event: MonitorEvent):
        """Publish event to event bus.

        Args:
            event: Event to publish
        """
        await self.event_bus.publish(event)
        logger.debug(f"{self.name}: Published {event.event_type} event")

    def is_running(self) -> bool:
        """Check if monitor is running.

        Returns:
            True if running, False otherwise
        """
        return self.running

    def get_name(self) -> str:
        """Get monitor name.

        Returns:
            Monitor name
        """
        return self.name

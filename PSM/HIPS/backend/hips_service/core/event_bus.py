"""Event bus for distributing monitoring events."""

import asyncio
from typing import Callable, List, Dict, Any
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class MonitorEvent:
    """Monitoring event data structure."""

    timestamp: datetime
    event_type: str  # process_create, file_modify, network_connect, etc.
    platform: str
    severity: str  # low, medium, high, critical
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary.

        Returns:
            Dictionary representation of event
        """
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result


class EventBus:
    """Event bus for publishing and subscribing to monitoring events."""

    def __init__(self, max_queue_size: int = 10000):
        """Initialize event bus.

        Args:
            max_queue_size: Maximum size of event queue
        """
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._event_queue = asyncio.Queue(maxsize=max_queue_size)
        self._running = False
        self._processor_task = None
        self._stats = {
            'events_published': 0,
            'events_processed': 0,
            'events_dropped': 0,
            'callback_failures': 0,
        }

    def subscribe(self, event_type: str, callback: Callable[[MonitorEvent], Any]):
        """Subscribe to specific event types.

        Args:
            event_type: Type of event to subscribe to (or '*' for all)
            callback: Callback function to invoke on event
        """
        self._subscribers[event_type].append(callback)
        logger.info(f"Subscriber added for event type: {event_type}")

    def unsubscribe(self, event_type: str, callback: Callable):
        """Unsubscribe from event type.

        Args:
            event_type: Event type to unsubscribe from
            callback: Callback to remove
        """
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(callback)
                logger.info(f"Subscriber removed for event type: {event_type}")
            except ValueError:
                pass

    async def publish(self, event: MonitorEvent):
        """Publish event to all subscribers.

        Args:
            event: Event to publish
        """
        try:
            self._event_queue.put_nowait(event)
            self._stats['events_published'] += 1
        except asyncio.QueueFull:
            self._stats['events_dropped'] += 1
            logger.warning(f"Event queue full, dropping event: {event.event_type}")

    async def process_events(self):
        """Process events from queue."""
        self._running = True
        logger.info("Event bus processor started")

        while self._running:
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
                failures = await self._dispatch_event(event)
                self._stats['events_processed'] += 1
                self._stats['callback_failures'] += failures
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing event: {e}", exc_info=True)

        logger.info("Event bus processor stopped")

    async def _dispatch_event(self, event: MonitorEvent) -> int:
        """Dispatch event to subscribers. Returns number of failed callbacks."""
        # Get specific subscribers
        subscribers = self._subscribers.get(event.event_type, [])

        # Add wildcard subscribers
        subscribers.extend(self._subscribers.get('*', []))

        failures = 0
        for callback in subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                failures += 1
                logger.error(f"Error in subscriber callback: {e}", exc_info=True)

        return failures

    async def start(self):
        """Start event bus processor."""
        if not self._running:
            self._processor_task = asyncio.create_task(self.process_events())

    async def stop(self):
        """Stop event bus processor."""
        self._running = False
        if self._processor_task:
            await self._processor_task

    def get_stats(self) -> Dict[str, int]:
        """Get event bus statistics.

        Returns:
            Dictionary of statistics
        """
        return {
            **self._stats,
            'queue_size': self._event_queue.qsize()
        }


# Global event bus instance
_event_bus: EventBus = None


def get_event_bus() -> EventBus:
    """Get global event bus instance.

    Returns:
        EventBus instance
    """
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus

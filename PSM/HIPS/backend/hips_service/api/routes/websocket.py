"""WebSocket routes for real-time updates."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List
import json
import asyncio
import logging

from hips_service.core.event_bus import MonitorEvent

logger = logging.getLogger(__name__)

router = APIRouter()

# Active WebSocket connections
active_connections: List[WebSocket] = []

# Event bus reference (injected by main)
_event_bus = None


async def _event_bus_callback(event: MonitorEvent):
    """Async event bus callback used for websocket broadcasting."""
    await broadcast_event(event)


def set_event_bus(event_bus):
    """Set event bus reference and register the broadcast callback once at startup."""
    global _event_bus
    _event_bus = event_bus
    # Register exactly once here — not lazily per connection — so concurrent
    # WebSocket handshakes can never cause duplicate subscriptions.
    _event_bus.subscribe('*', _event_bus_callback)


@router.websocket("/events")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time event streaming."""
    await websocket.accept()
    active_connections.append(websocket)
    logger.info(f"WebSocket client connected. Total connections: {len(active_connections)}")

    try:
        # Keep connection alive and listen for client messages
        while True:
            try:
                # Wait for client messages (ping/pong, filters, etc.)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                # Handle client messages if needed
            except asyncio.TimeoutError:
                # No message received, continue
                continue

    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)
        logger.info(f"WebSocket client disconnected. Total connections: {len(active_connections)}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        if websocket in active_connections:
            active_connections.remove(websocket)


async def broadcast_event(event: MonitorEvent):
    """Broadcast event to all connected WebSocket clients."""
    if not active_connections:
        return

    # Convert event to JSON
    event_data = event.to_dict()
    message = json.dumps({
        "type": "event",
        "data": event_data
    })

    # Send to all connected clients
    disconnected = []
    for connection in active_connections:
        try:
            await connection.send_text(message)
        except Exception as e:
            logger.error(f"Error sending to WebSocket client: {e}")
            disconnected.append(connection)

    # Remove disconnected clients
    for conn in disconnected:
        if conn in active_connections:
            active_connections.remove(conn)

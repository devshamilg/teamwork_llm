from typing import Any, Union
import uuid

from fastapi import WebSocket


class ConnectionManager:
    """Manages active WebSocket connections grouped by room_id."""

    def __init__(self) -> None:
        self.active_connections: dict[str, list[WebSocket]] = {}

    @staticmethod
    def _normalize_id(room_id: Union[uuid.UUID, str]) -> str:
        return str(room_id)

    async def connect(
        self,
        room_id: Union[uuid.UUID, str],
        websocket: WebSocket,
    ) -> None:
        await websocket.accept()
        key = self._normalize_id(room_id)
        if key not in self.active_connections:
            self.active_connections[key] = []
        self.active_connections[key].append(websocket)

    def disconnect(
        self,
        room_id: Union[uuid.UUID, str],
        websocket: WebSocket,
    ) -> None:
        key = self._normalize_id(room_id)
        if key in self.active_connections:
            if websocket in self.active_connections[key]:
                self.active_connections[key].remove(websocket)
            if not self.active_connections[key]:
                del self.active_connections[key]

    async def send_personal_message(
        self,
        websocket: WebSocket,
        message: dict[str, Any],
    ) -> None:
        await websocket.send_json(message)

    async def broadcast(
        self,
        room_id: Union[uuid.UUID, str],
        message: dict[str, Any],
    ) -> None:
        key = self._normalize_id(room_id)
        connections = list(self.active_connections.get(key, []))
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception:
                # Disconnect stale/broken connections safely
                self.disconnect(room_id, connection)


manager = ConnectionManager()

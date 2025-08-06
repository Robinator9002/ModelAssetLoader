# backend/main.py
import logging
import json
from typing import List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# --- Refactored Imports ---
# Import the download_tracker singleton directly.
from core.file_management.download_tracker import download_tracker

# Import the new API routers.
from routers import models, file_manager, ui

# --- Logging Configuration ---
# Set up a consistent logging format for the entire application.
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s",
)
logger = logging.getLogger(__name__)


# --- FastAPI Application Instance ---
# The main application object is created here.
app = FastAPI(
    title="M.A.L. - Model Asset Loader API",
    description="API for searching external model sources, managing local model files, "
    "and configuring/managing AI UI environments.",
    version="1.8.0-refactored",  # Updated version to reflect changes
)

# --- CORS Middleware ---
# Configure Cross-Origin Resource Sharing to allow the frontend to communicate with the backend.
origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Include API Routers ---
# This is the core of the refactoring. Instead of defining all endpoints in this
# file, we include the organized, feature-specific routers.
logger.info("Including API routers...")
app.include_router(models.router)
app.include_router(file_manager.router)
app.include_router(ui.router)
logger.info("API routers included successfully.")


# --- WebSocket Connection Manager ---
# This logic remains in main.py as it's a core part of the application's
# real-time infrastructure, tightly coupled with the app lifecycle.
class ConnectionManager:
    """Manages active WebSocket connections for real-time broadcasting."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected: {websocket.client}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected: {websocket.client}")

    async def broadcast(self, message: str):
        """Sends a message to all currently connected WebSocket clients."""
        if not self.active_connections:
            return
        # Iterate over a copy to safely handle disconnections during broadcast.
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                self.disconnect(connection)


manager = ConnectionManager()


# --- WebSocket Endpoint for Real-time Updates ---
@app.websocket("/ws/downloads")
async def websocket_endpoint(websocket: WebSocket):
    """Handles WebSocket connections for real-time task updates."""
    await manager.connect(websocket)

    # Define the callback that our services will use to send updates.
    async def broadcast_status_update(data: dict):
        await manager.broadcast(json.dumps(data, default=str))

    # Register the callback with the relevant services.
    download_tracker.set_broadcast_callback(broadcast_status_update)
    # Note: If ui_manager needs to broadcast, it would also be set here.
    # For now, it uses the download_tracker, so this is sufficient.

    try:
        # Send the initial state of all tasks to the newly connected client.
        initial_statuses = download_tracker.get_all_statuses()
        await websocket.send_text(
            json.dumps({"type": "initial_state", "downloads": initial_statuses})
        )
        # Keep the connection alive.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        # If this was the last client, clear the callback to prevent unnecessary work.
        if not manager.active_connections:
            download_tracker.set_broadcast_callback(None)
            logger.info("Last WebSocket client disconnected, clearing broadcast callback.")


# --- Main Execution Block ---
# This block allows the application to be run directly for development.
if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting M.A.L. API server (v{app.version}) for development...")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True, workers=1)

// frontend/src/api/websocket.tsx
import { WS_BASE_URL } from './client';

/**
 * @file This module contains the logic for establishing and managing
 * the WebSocket connection to the download tracker service.
 */

// --- PHASE 2.4 MODIFICATION: Define an interface for all WebSocket lifecycle callbacks ---
interface WebSocketCallbacks {
    onOpen: () => void;
    onMessage: (data: any) => void;
    onClose: (event: CloseEvent) => void;
    onError: (event: Event) => void;
}

// --- WebSocket Connection ---

/**
 * Establishes a WebSocket connection to the download tracker endpoint.
 * It sets up handlers for message receiving, errors, and connection lifecycle events.
 *
 * @param {WebSocketCallbacks} callbacks - An object containing the callback functions for lifecycle events.
 * @returns {WebSocket} The WebSocket instance, allowing the caller to manage the connection (e.g., close it).
 */
export const connectToDownloadTracker = (callbacks: WebSocketCallbacks): WebSocket => {
    const wsUrl = `${WS_BASE_URL}/ws/downloads`;
    const ws = new WebSocket(wsUrl);

    /**
     * Called when the WebSocket connection is successfully opened.
     */
    ws.onopen = () => {
        callbacks.onOpen();
    };

    /**
     * Called when a message is received from the server.
     * It parses the JSON message and passes the data to the provided callback.
     */
    ws.onmessage = (event: MessageEvent) => {
        try {
            const data = JSON.parse(event.data);
            callbacks.onMessage(data);
        } catch (e) {
            console.error('Error parsing WebSocket message:', e);
        }
    };

    /**
     * Called when a WebSocket error occurs.
     */
    ws.onerror = (event: Event) => {
        callbacks.onError(event);
    };

    /**
     * Called when the WebSocket connection is closed.
     */
    ws.onclose = (event: CloseEvent) => {
        callbacks.onClose(event);
    };

    return ws;
};

// frontend/src/api/websocket.tsx
import { WS_BASE_URL } from './client';

/**
 * @file This module contains the logic for establishing and managing
 * the WebSocket connection to the download tracker service.
 */

// --- WebSocket Connection ---

/**
 * Establishes a WebSocket connection to the download tracker endpoint.
 * It sets up handlers for message receiving, errors, and connection lifecycle events.
 *
 * @param {(data: any) => void} onMessage - The callback function to be executed
 * when a message is received from the WebSocket server. It receives the parsed JSON data.
 * @returns {WebSocket} The WebSocket instance, allowing the caller to manage the connection (e.g., close it).
 */
export const connectToDownloadTracker = (onMessage: (data: any) => void): WebSocket => {
    const wsUrl = `${WS_BASE_URL}/ws/downloads`;
    const ws = new WebSocket(wsUrl);

    /**
     * Called when the WebSocket connection is successfully opened.
     */
    ws.onopen = () => {
        console.log('WebSocket connection established.');
    };

    /**
     * Called when a message is received from the server.
     * It parses the JSON message and passes the data to the provided callback.
     * @param {MessageEvent} event - The event object containing the message data.
     */
    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            onMessage(data);
        } catch (e) {
            console.error('Error parsing WebSocket message:', e);
        }
    };

    /**
     * Called when a WebSocket error occurs.
     * @param {Event} event - The error event.
     */
    ws.onerror = (event) => {
        console.error('WebSocket error observed:', event);
    };

    /**
     * Called when the WebSocket connection is closed.
     * Logs the details of the closure event.
     * @param {CloseEvent} event - The close event.
     */
    ws.onclose = (event) => {
        console.log(
            `WebSocket connection closed. Code: ${event.code}, Reason: '${event.reason}', Was clean: ${event.wasClean}`,
        );
    };

    return ws;
};

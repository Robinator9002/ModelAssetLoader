// frontend/src/api/client.ts
import axios, { type AxiosInstance } from 'axios';

// --- Constants ---

/**
 * @constant {string} API_BASE_URL
 * The base URL for all HTTP API requests.
 * All API calls made through the apiClient will be prefixed with this URL.
 */
const API_BASE_URL = 'http://localhost:8000/api';

/**
 * @constant {string} WS_BASE_URL
 * The base URL for WebSocket connections.
 * This is used to establish real-time communication channels with the server.
 */
export const WS_BASE_URL = 'ws://localhost:8000';

// --- API Client ---

/**
 * @description A pre-configured Axios instance for all HTTP requests.
 * This instance is set up with the base URL and default headers,
 * ensuring consistency across all API calls. It simplifies making
 * requests by abstracting away the common configuration.
 *
 * @type {AxiosInstance}
 */
const apiClient: AxiosInstance = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

/**
 * @description Default export of the configured Axios client.
 * This allows other parts of the application to import this single,
 * pre-configured instance for making API requests, promoting code
 * reuse and simplifying maintenance.
 * e.g., `import apiClient from '~/api/client';`
 */
export default apiClient;

// frontend/src/api/index.tsx

/**
 * @file This file serves as the main entry point for the entire API module.
 * It uses the "barrel" pattern to re-export all functions, types, and the
 * default API client from the other specialized modules in this directory.
 *
 * This approach allows other parts of the application to import anything they
 * need from a single, consistent path (e.g., `import { searchModels } from '~/api'`)
 * while keeping the internal structure of the API module organized and maintainable.
 */

// --- Re-export all named exports from modules ---

// Export all type definitions and interfaces
export * from './types';

// Export all API functions from the service modules
export * from './services/ui';
export * from './services/models';
export * from './services/fileManager';

// Export the WebSocket connection function
export * from './websocket';

// --- Re-export the default export ---

// Export the default apiClient instance for direct use
export { default } from './client';

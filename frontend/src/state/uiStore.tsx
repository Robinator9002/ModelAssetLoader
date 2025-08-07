// frontend/src/state/uiStore.ts
import { create } from 'zustand';
import {
    // API functions for UI management
    listAvailableUisAPI,
    getUiStatusesAPI,
    // Type definitions from the API layer
    type AvailableUiItem,
    type ManagedUiStatus,
} from '~/api';

/**
 * @interface UiState
 * Defines the complete shape of the UI management store's state. It holds
 * the list of all UIs that can be installed and the live status of any UI
 * instances that are currently managed by the application.
 */
interface UiState {
    // State properties
    availableUis: AvailableUiItem[];
    // --- REFACTOR: This state now holds an array of the updated ManagedUiStatus objects,
    // each representing a unique instance with an installation_id and display_name. ---
    uiStatuses: ManagedUiStatus[];
    isLoading: boolean;

    // Actions (functions to modify the state)
    fetchUiData: () => Promise<void>;
}

/**
 * `useUiStore` is a custom hook created by Zustand.
 *
 * This store is the single source of truth for the state of all AI UI environments
 * known to the application. It encapsulates the lists of available UI types and
 * all installed instances, providing a single action to refresh this data from the backend.
 */
export const useUiStore = create<UiState>((set) => ({
    // --- INITIAL STATE ---
    availableUis: [],
    uiStatuses: [],
    isLoading: false,

    // --- ACTIONS ---

    /**
     * Fetches all UI-related data from the backend. This includes both the list of
     * all possible UIs that can be installed and the current statuses of any UI
     * instances that have already been installed or adopted.
     */
    fetchUiData: async () => {
        set({ isLoading: true });
        try {
            // Fetch both lists in parallel for better performance.
            const [uis, statuses] = await Promise.all([listAvailableUisAPI(), getUiStatusesAPI()]);

            // Thanks to our centralized type definitions, no logic change is needed here.
            // The `statuses.items` array will automatically conform to the new,
            // richer ManagedUiStatus interface.
            set({
                availableUis: uis,
                uiStatuses: statuses.items,
            });
        } catch (error) {
            console.error('Failed to fetch UI environment data:', error);
            // If the fetch fails, we reset to a clean state to avoid showing stale data.
            set({ availableUis: [], uiStatuses: [] });
        } finally {
            set({ isLoading: false });
        }
    },
}));

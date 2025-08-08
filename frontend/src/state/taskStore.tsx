// frontend/src/state/taskStore.ts
import { create } from 'zustand';
import {
    // API functions
    connectToDownloadTracker,
    dismissDownloadAPI,
    // Type definitions
    type DownloadStatus,
} from '~/api';
import { useUiStore } from './uiStore';
import { useConfigStore } from './configStore';

/**
 * @interface TaskState
 * Defines the shape of the store responsible for managing all background tasks
 * and the real-time WebSocket connection that reports their status.
 */
interface TaskState {
    // State properties
    activeTasks: Map<string, DownloadStatus>;
    tasksToAutoConfigure: Set<string>;
    ws: WebSocket | null;

    // Actions
    connect: () => void;
    disconnect: () => void;
    addTaskToAutoConfigure: (taskId: string) => void;
    dismissTask: (taskId: string) => Promise<void>;
}

/**
 * `useTaskStore` is a custom hook created by Zustand.
 *
 * This store is the single source of truth for all background tasks (downloads,
 * installations, running processes). It encapsulates the WebSocket connection
 * logic, preventing it from being tied to the lifecycle of any single component.
 * It also orchestrates interactions between other stores when a task completes,
 * for example, by telling the `uiStore` to refresh its data after an install.
 */
export const useTaskStore = create<TaskState>((set, get) => ({
    // --- INITIAL STATE ---
    activeTasks: new Map(),
    tasksToAutoConfigure: new Set(),
    ws: null,

    // --- ACTIONS ---

    /**
     * Establishes and manages the WebSocket connection. If a connection already
     * exists, this function does nothing. It includes logic for handling incoming
     * messages and orchestrating state updates across the application.
     */
    connect: () => {
        if (get().ws) {
            console.log('WebSocket connection already established.');
            return;
        }

        console.log('Establishing WebSocket connection...');
        const ws = connectToDownloadTracker((data: any) => {
            // --- WebSocket Message Handler ---
            switch (data.type) {
                case 'initial_state':
                    set({
                        activeTasks: new Map(
                            (data.downloads || []).map((s: DownloadStatus) => [s.download_id, s]),
                        ),
                    });
                    break;

                case 'update':
                    const status: DownloadStatus = data.data;
                    if (status?.download_id) {
                        set((state) => ({
                            activeTasks: new Map(state.activeTasks).set(status.download_id, status),
                        }));

                        // --- Cross-Store Orchestration ---
                        if (status.status === 'completed') {
                            // If a UI-related task completes, refresh the UI data.
                            if (status.repo_id?.includes('UI')) {
                                useUiStore.getState().fetchUiData();
                            }

                            // --- PHASE 2.2 MODIFICATION: Handle Auto-Configuration ---
                            // Check if the completed task was marked for auto-configuration
                            // AND if the backend provided the necessary installation_id.
                            if (
                                get().tasksToAutoConfigure.has(status.download_id) &&
                                status.installation_id
                            ) {
                                // The `repo_id` for UI tasks is the `ui_name` (e.g., 'ComfyUI').
                                const uiName = status.repo_id;
                                const { availableUis } = useUiStore.getState();
                                const uiInfo = availableUis.find((ui) => ui.ui_name === uiName);

                                if (uiInfo) {
                                    // Trigger the configuration update in the config store,
                                    // using the new installation_id.
                                    console.log(
                                        `Auto-configuring to new instance: ${status.installation_id}`,
                                    );
                                    useConfigStore.getState().updateConfiguration({
                                        config_mode: 'automatic',
                                        automatic_mode_ui: status.installation_id,
                                        profile: uiInfo.default_profile_name,
                                    });
                                } else {
                                    console.warn(
                                        `Could not auto-configure: UI type '${uiName}' not found in availableUis.`,
                                    );
                                }

                                // Clean up the task from the auto-configure set.
                                set((state) => {
                                    const newSet = new Set(state.tasksToAutoConfigure);
                                    newSet.delete(status.download_id);
                                    return { tasksToAutoConfigure: newSet };
                                });
                            }
                        }
                    }
                    break;

                case 'remove':
                    if (data.download_id) {
                        set((state) => {
                            const newMap = new Map(state.activeTasks);
                            newMap.delete(data.download_id);
                            return { activeTasks: newMap };
                        });
                    }
                    break;
            }
        });

        set({ ws });
    },

    /**
     * Gracefully closes the WebSocket connection.
     */
    disconnect: () => {
        get().ws?.close();
        set({ ws: null });
    },

    /**
     * Marks a specific task ID for a follow-up configuration action upon its completion.
     * @param {string} taskId - The ID of the task to mark.
     */
    addTaskToAutoConfigure: (taskId: string) => {
        set((state) => ({
            tasksToAutoConfigure: new Set(state.tasksToAutoConfigure).add(taskId),
        }));
    },

    /**
     * Dismisses a completed or failed task. It calls the backend API to remove
     * the task from the server's tracker and then removes it from the local state.
     * This fixes the state desynchronization bug.
     * @param {string} taskId - The ID of the task to dismiss.
     */
    dismissTask: async (taskId: string) => {
        try {
            // Call the API first to ensure the backend is updated.
            await dismissDownloadAPI(taskId);
            // Only update local state after the API call succeeds.
            set((state) => {
                const newMap = new Map(state.activeTasks);
                newMap.delete(taskId);
                return { activeTasks: newMap };
            });
        } catch (error) {
            console.error(`Failed to dismiss task ${taskId}:`, error);
            // Optionally, we could show an error to the user here.
        }
    },
}));

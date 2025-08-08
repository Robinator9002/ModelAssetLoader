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

// --- PHASE 2.4 MODIFICATION: Define a strict type for WebSocket connection status ---
export type WsConnectionStatus = 'connecting' | 'connected' | 'reconnecting' | 'disconnected';

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
    // --- PHASE 2.4 MODIFICATION: Add connection status and management state ---
    wsStatus: WsConnectionStatus;
    reconnectTimeoutId: NodeJS.Timeout | null;

    // Actions
    initializeConnection: () => void; // Renamed from 'connect'
    disconnect: () => void;
    addTaskToAutoConfigure: (taskId: string) => void;
    dismissTask: (taskId: string) => Promise<void>;
}

const MAX_RECONNECT_DELAY = 30000; // 30 seconds

/**
 * `useTaskStore` is a custom hook created by Zustand.
 *
 * This store is the single source of truth for all background tasks (downloads,
 * installations, running processes). It encapsulates the WebSocket connection
 * logic, making it resilient to network drops and server restarts.
 */
export const useTaskStore = create<TaskState>((set, get) => {
    // --- Helper function for WebSocket connection logic ---
    let reconnectAttempts = 0;

    const connect = () => {
        // Prevent multiple parallel connection attempts
        if (get().ws && get().ws?.readyState < 2) {
            console.log('WebSocket connection attempt already in progress or established.');
            return;
        }

        console.log(`Attempting to connect (Attempt: ${reconnectAttempts + 1})...`);
        set({ wsStatus: reconnectAttempts > 0 ? 'reconnecting' : 'connecting' });

        const ws = connectToDownloadTracker({
            onOpen: () => {
                console.log('WebSocket connection established.');
                reconnectAttempts = 0; // Reset on successful connection
                set({ wsStatus: 'connected' });
            },
            onMessage: (data: any) => {
                // --- WebSocket Message Handler ---
                switch (data.type) {
                    case 'initial_state':
                        set({
                            activeTasks: new Map(
                                (data.downloads || []).map((s: DownloadStatus) => [
                                    s.download_id,
                                    s,
                                ]),
                            ),
                        });
                        break;

                    case 'update':
                        const status: DownloadStatus = data.data;
                        if (status?.download_id) {
                            set((state) => ({
                                activeTasks: new Map(state.activeTasks).set(
                                    status.download_id,
                                    status,
                                ),
                            }));

                            // --- Cross-Store Orchestration ---
                            if (status.status === 'completed') {
                                if (status.repo_id?.includes('UI')) {
                                    useUiStore.getState().fetchUiData();
                                }

                                if (
                                    get().tasksToAutoConfigure.has(status.download_id) &&
                                    status.installation_id
                                ) {
                                    const uiName = status.repo_id;
                                    const { availableUis } = useUiStore.getState();
                                    const uiInfo = availableUis.find((ui) => ui.ui_name === uiName);

                                    if (uiInfo) {
                                        console.log(
                                            `Auto-configuring to new instance: ${status.installation_id}`,
                                        );
                                        useConfigStore.getState().updateConfiguration({
                                            config_mode: 'automatic',
                                            automatic_mode_ui: status.installation_id,
                                            profile: uiInfo.default_profile_name,
                                        });
                                    }

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
            },
            onClose: () => {
                console.log('WebSocket connection closed.');
                set({ ws: null, wsStatus: 'reconnecting' });

                // Exponential backoff for reconnection
                const delay = Math.min(1000 * 2 ** reconnectAttempts, MAX_RECONNECT_DELAY);
                reconnectAttempts++;

                console.log(`Will attempt to reconnect in ${delay / 1000}s...`);
                const timeoutId = setTimeout(connect, delay);
                set({ reconnectTimeoutId: timeoutId });
            },
            onError: (error) => {
                console.error('WebSocket error observed:', error);
                // The onClose event will be triggered automatically after an error,
                // so the reconnection logic will be handled there.
            },
        });

        set({ ws });
    };

    return {
        // --- INITIAL STATE ---
        activeTasks: new Map(),
        tasksToAutoConfigure: new Set(),
        ws: null,
        wsStatus: 'disconnected',
        reconnectTimeoutId: null,

        // --- ACTIONS ---
        initializeConnection: () => {
            if (get().wsStatus === 'disconnected') {
                connect();
            }
        },

        disconnect: () => {
            const { ws, reconnectTimeoutId } = get();
            if (reconnectTimeoutId) {
                clearTimeout(reconnectTimeoutId);
            }
            if (ws) {
                ws.close();
            }
            set({ ws: null, wsStatus: 'disconnected', reconnectTimeoutId: null });
            reconnectAttempts = 0;
        },

        addTaskToAutoConfigure: (taskId: string) => {
            set((state) => ({
                tasksToAutoConfigure: new Set(state.tasksToAutoConfigure).add(taskId),
            }));
        },

        dismissTask: async (taskId: string) => {
            try {
                await dismissDownloadAPI(taskId);
                set((state) => {
                    const newMap = new Map(state.activeTasks);
                    newMap.delete(taskId);
                    return { activeTasks: newMap };
                });
            } catch (error) {
                console.error(`Failed to dismiss task ${taskId}:`, error);
            }
        },
    };
});

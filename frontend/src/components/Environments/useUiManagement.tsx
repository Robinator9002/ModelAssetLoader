// frontend/src/components/Environments/useUiManagement.tsx
import { useState, useMemo, useCallback } from 'react';
import {
    // API functions
    installUiAPI,
    runUiAPI,
    stopUiAPI,
    deleteUiAPI,
    repairUiAPI,
    finalizeAdoptionAPI,
    // Type definitions
    type AvailableUiItem,
    type UiNameType,
    type UiInstallRequest,
    type DownloadStatus,
} from '~/api';
import { useUiStore } from '../../state/uiStore';
import { useTaskStore } from '../../state/taskStore';

/**
 * @hook useUiManagement
 *
 * @description
 * This custom hook encapsulates all the business logic, state management, and
 * API interactions for the UI Environments page. It handles fetching UI data,
 * managing modal states (install, adopt, delete), and orchestrating all user
 * actions like installing, running, stopping, and deleting UIs.
 *
 * By extracting this logic from the `UiManagementPage` component, we achieve a
 * clean separation of concerns, making both the logic and the presentation
 * easier to manage and test.
 *
 * @returns An object containing all the state and action handlers needed by the
 * `UiManagementPage` component to render its UI.
 */
export const useUiManagement = () => {
    // --- State from Zustand Stores ---
    const { availableUis, uiStatuses, fetchUiData, isLoading } = useUiStore();
    const { activeTasks, addTaskToAutoConfigure } = useTaskStore();

    // --- Local View State (for modals) ---
    const [isInstallModalOpen, setIsInstallModalOpen] = useState(false);
    const [uiToInstall, setUiToInstall] = useState<AvailableUiItem | null>(null);
    const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
    const [uiToDelete, setUiToDelete] = useState<UiNameType | null>(null);
    const [isAdoptModalOpen, setIsAdoptModalOpen] = useState(false);

    // --- Memoized Derived State ---

    // Checks if a UI is involved in a pending or in-progress task.
    const isUiBusy = useCallback(
        (uiName: UiNameType): boolean => {
            return Array.from(activeTasks.values()).some(
                (d: DownloadStatus) =>
                    d.filename === uiName &&
                    ['pending', 'downloading', 'running'].includes(d.status),
            );
        },
        [activeTasks],
    );

    // Combines available UI data with live status data for rendering.
    const combinedUiData = useMemo(() => {
        const statusMap = new Map(uiStatuses.map((s) => [s.ui_name, s]));
        return availableUis.map((ui: AvailableUiItem) => {
            const status = statusMap.get(ui.ui_name);
            return {
                ...ui,
                is_installed: status?.is_installed ?? false,
                is_running: status?.is_running ?? false,
                install_path: status?.install_path,
                running_task_id: status?.running_task_id,
            };
        });
    }, [availableUis, uiStatuses]);

    // --- Action Handlers ---

    const handleInstall = useCallback(
        async (request: UiInstallRequest) => {
            try {
                const response = await installUiAPI(request);
                if (response.success && response.set_as_active_on_completion) {
                    addTaskToAutoConfigure(response.task_id);
                }
            } catch (error: any) {
                console.error(`Failed to start installation for ${request.ui_name}:`, error);
                // TODO: Implement a user-facing error notification system.
            }
            setIsInstallModalOpen(false);
        },
        [addTaskToAutoConfigure],
    );

    const handleRun = useCallback(async (uiName: UiNameType) => {
        try {
            await runUiAPI(uiName);
        } catch (error: any) {
            console.error(`Failed to start UI ${uiName}:`, error);
        }
    }, []);

    const handleStop = useCallback(async (taskId: string) => {
        try {
            await stopUiAPI(taskId);
        } catch (error: any) {
            console.error(`Failed to stop UI task ${taskId}:`, error);
        }
    }, []);

    const handleDelete = useCallback(async () => {
        if (!uiToDelete) return;
        try {
            await deleteUiAPI(uiToDelete);
            fetchUiData(); // Manually trigger a refresh after deletion.
        } catch (error: any) {
            console.error(`Failed to delete UI ${uiToDelete}:`, error);
        }
        setIsDeleteConfirmOpen(false);
        setUiToDelete(null);
    }, [uiToDelete, fetchUiData]);

    const handleRepair = useCallback(
        async (uiName: UiNameType, path: string, issuesToFix: string[]) => {
            try {
                const response = await repairUiAPI({
                    ui_name: uiName,
                    path,
                    issues_to_fix: issuesToFix,
                });
                if (response.success) {
                    addTaskToAutoConfigure(response.task_id);
                }
            } catch (error: any) {
                console.error(`Failed to start repair for ${uiName}:`, error);
            }
            setIsAdoptModalOpen(false);
        },
        [addTaskToAutoConfigure],
    );

    const handleFinalizeAdoption = useCallback(
        async (uiName: UiNameType, path: string) => {
            try {
                await finalizeAdoptionAPI({ ui_name: uiName, path });
                fetchUiData(); // Refresh UI data after successful adoption.
            } catch (error: any) {
                console.error(`Failed to finalize adoption for ${uiName}:`, error);
            }
            setIsAdoptModalOpen(false);
        },
        [fetchUiData],
    );

    // --- Modal Control Handlers ---
    const openInstallModal = (ui: AvailableUiItem) => {
        setUiToInstall(ui);
        setIsInstallModalOpen(true);
    };

    const requestDelete = (uiName: UiNameType) => {
        setUiToDelete(uiName);
        setIsDeleteConfirmOpen(true);
    };

    // --- Return Value ---
    return {
        // State
        isLoading,
        combinedUiData,
        isInstallModalOpen,
        uiToInstall,
        isDeleteConfirmOpen,
        uiToDelete,
        isAdoptModalOpen,
        availableUis, // Pass this through for the Adopt modal
        // Actions
        isUiBusy,
        handleInstall,
        handleRun,
        handleStop,
        handleDelete,
        handleRepair,
        handleFinalizeAdoption,
        openInstallModal,
        requestDelete,
        // Setters for closing modals from the component
        setIsInstallModalOpen,
        setIsDeleteConfirmOpen,
        setUiToDelete,
        setIsAdoptModalOpen,
    };
};

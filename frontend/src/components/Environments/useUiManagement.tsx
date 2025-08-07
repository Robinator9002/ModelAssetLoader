// frontend/src/components/Environments/useUiManagement.tsx
import { useState, useCallback } from 'react';
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
    type ManagedUiStatus,
} from '~/api';
import { useUiStore } from '../../state/uiStore';
import { useTaskStore } from '../../state/taskStore';

/**
 * @hook useUiManagement
 *
 * @description
 * This custom hook encapsulates all the business logic, state management, and
 * API interactions for the UI Environments page.
 *
 * @refactor This hook has been significantly updated to manage unique UI instances.
 * All actions (run, stop, delete) now operate on a specific `installation_id`.
 * It provides the main `UiManagementPage` with a clean, instance-based dataset
 * and the functions to interact with each instance.
 */
export const useUiManagement = () => {
    // --- State from Zustand Stores ---
    const { availableUis, uiStatuses, fetchUiData, isLoading } = useUiStore();
    // --- FIX: Expose activeTasks for use in the component ---
    const { activeTasks, addTaskToAutoConfigure } = useTaskStore();

    // --- Local View State (for modals) ---
    const [isInstallModalOpen, setIsInstallModalOpen] = useState(false);
    const [uiToInstall, setUiToInstall] = useState<AvailableUiItem | null>(null);
    const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
    const [uiToDelete, setUiToDelete] = useState<ManagedUiStatus | null>(null);
    const [isAdoptModalOpen, setIsAdoptModalOpen] = useState(false);

    // --- Derived State ---

    // Checks if a specific UI instance is involved in a pending or in-progress task.
    const isUiBusy = useCallback(
        (installationId: string): boolean => {
            const instance = uiStatuses.find((s) => s.installation_id === installationId);
            if (!instance) return false;

            return Array.from(activeTasks.values()).some(
                (task: DownloadStatus) =>
                    // Match running processes by their task ID
                    (task.repo_id === 'UI Process' &&
                        instance.running_task_id === task.download_id) ||
                    // Match install/repair tasks by their display name (filename)
                    (task.filename === instance.display_name &&
                        ['pending', 'downloading', 'running'].includes(task.status)),
            );
        },
        [activeTasks, uiStatuses],
    );

    // --- Action Handlers (now instance-based) ---

    const handleInstall = useCallback(
        async (request: UiInstallRequest) => {
            try {
                const response = await installUiAPI(request);
                if (response.success && response.set_as_active_on_completion) {
                    addTaskToAutoConfigure(response.task_id);
                }
            } catch (error: any) {
                console.error(`Failed to start installation for ${request.display_name}:`, error);
            }
            setIsInstallModalOpen(false);
        },
        [addTaskToAutoConfigure],
    );

    const handleRun = useCallback(async (installationId: string) => {
        try {
            await runUiAPI(installationId);
        } catch (error: any) {
            console.error(`Failed to start UI instance ${installationId}:`, error);
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
            await deleteUiAPI(uiToDelete.installation_id);
            fetchUiData();
        } catch (error: any) {
            console.error(`Failed to delete UI ${uiToDelete.display_name}:`, error);
        }
        setIsDeleteConfirmOpen(false);
        setUiToDelete(null);
    }, [uiToDelete, fetchUiData]);

    const handleRepair = useCallback(
        async (uiName: UiNameType, displayName: string, path: string, issuesToFix: string[]) => {
            try {
                const response = await repairUiAPI({
                    ui_name: uiName,
                    display_name: displayName,
                    path,
                    issues_to_fix: issuesToFix,
                });
                if (response.success) {
                    addTaskToAutoConfigure(response.task_id);
                }
            } catch (error: any) {
                console.error(`Failed to start repair for ${displayName}:`, error);
            }
            setIsAdoptModalOpen(false);
        },
        [addTaskToAutoConfigure],
    );

    const handleFinalizeAdoption = useCallback(
        async (uiName: UiNameType, displayName: string, path: string) => {
            try {
                await finalizeAdoptionAPI({ ui_name: uiName, display_name: displayName, path });
                fetchUiData();
            } catch (error: any) {
                console.error(`Failed to finalize adoption for ${displayName}:`, error);
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

    const requestDelete = (ui: ManagedUiStatus) => {
        setUiToDelete(ui);
        setIsDeleteConfirmOpen(true);
    };

    // --- Return Value ---
    return {
        // State
        isLoading,
        installedUis: uiStatuses,
        availableUis,
        activeTasks, // --- FIX: Pass activeTasks through to the component ---
        isInstallModalOpen,
        uiToInstall,
        isDeleteConfirmOpen,
        uiToDelete,
        isAdoptModalOpen,
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
        // Setters
        setIsInstallModalOpen,
        setIsDeleteConfirmOpen,
        setUiToDelete,
        setIsAdoptModalOpen,
    };
};

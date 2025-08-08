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
import { useUiStore } from '../state/uiStore';
import { useTaskStore } from '../state/taskStore';

/**
 * @hook useUiManagement
 *
 * @description
 * This custom hook encapsulates all the business logic, state management, and
 * API interactions for the UI Environments page.
 */
export const useUiManagement = () => {
    // --- State from Zustand Stores ---
    const { availableUis, uiStatuses, fetchUiData, isLoading } = useUiStore();
    const { activeTasks, addTaskToAutoConfigure } = useTaskStore();

    // --- Local View State (for modals) ---
    const [isInstallModalOpen, setIsInstallModalOpen] = useState(false);
    const [uiToInstall, setUiToInstall] = useState<AvailableUiItem | null>(null);
    const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
    const [uiToDelete, setUiToDelete] = useState<ManagedUiStatus | null>(null);
    const [isAdoptModalOpen, setIsAdoptModalOpen] = useState(false);
    // --- NEW: State for the Edit Modal ---
    const [isEditModalOpen, setIsEditModalOpen] = useState(false);
    const [uiToEdit, setUiToEdit] = useState<ManagedUiStatus | null>(null);

    // --- Derived State ---
    const isUiBusy = useCallback(
        (installationId: string): boolean => {
            const instance = uiStatuses.find((s) => s.installation_id === installationId);
            if (!instance) return false;

            return Array.from(activeTasks.values()).some(
                (task: DownloadStatus) =>
                    (task.repo_id === 'UI Process' &&
                        instance.running_task_id === task.download_id) ||
                    (task.filename === instance.display_name &&
                        ['pending', 'downloading', 'running'].includes(task.status)),
            );
        },
        [activeTasks, uiStatuses],
    );

    // --- Action Handlers ---

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

    // --- NEW: Handler for successful update ---
    const handleUpdateSuccess = useCallback(() => {
        setIsEditModalOpen(false);
        setUiToEdit(null);
        fetchUiData();
    }, [fetchUiData]);

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

    // --- NEW: Handlers to open/close the Edit Modal ---
    const openEditModal = (ui: ManagedUiStatus) => {
        setUiToEdit(ui);
        setIsEditModalOpen(true);
    };

    const closeEditModal = () => {
        setUiToEdit(null);
        setIsEditModalOpen(false);
    };

    // --- Return Value ---
    return {
        // State
        isLoading,
        installedUis: uiStatuses,
        availableUis,
        activeTasks,
        isInstallModalOpen,
        uiToInstall,
        isDeleteConfirmOpen,
        uiToDelete,
        isAdoptModalOpen,
        isEditModalOpen, // <-- NEW
        uiToEdit, // <-- NEW
        // Actions
        isUiBusy,
        handleInstall,
        handleRun,
        handleStop,
        handleDelete,
        handleUpdateSuccess, // <-- NEW
        handleRepair,
        handleFinalizeAdoption,
        openInstallModal,
        requestDelete,
        openEditModal, // <-- NEW
        // Setters
        setIsInstallModalOpen,
        setIsDeleteConfirmOpen,
        setUiToDelete,
        setIsAdoptModalOpen,
        closeEditModal, // <-- NEW
    };
};

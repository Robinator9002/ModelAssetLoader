// frontend/src/components/Environments/UiManagementPage.tsx
import React, { useState, useMemo, useCallback } from 'react';
import {
    // --- REFACTOR: Import API functions directly ---
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
    type DownloadStatus, // <-- FIX: Import DownloadStatus for typing
} from '~/api';
import {
    // --- FIX: Corrected store imports to be direct paths ---
    useUiStore,
} from '../../state/uiStore';
import { useTaskStore } from '../../state/taskStore';
import {
    // Icons
    Layers,
    Download,
    Trash2,
    Play,
    CheckCircle,
    Loader2,
    StopCircle,
    ClipboardCheck,
} from 'lucide-react';
// Component Imports
import InstallUiModal from './InstallUiModal';
import ConfirmModal from '../Layout/ConfirmModal';
import AdoptUiModal from './AdoptUiModal';

/**
 * @refactor This component is now self-sufficient, fetching its own data from
 * Zustand stores and containing its own logic for handling user actions by
 * calling the API directly. All `on...` props have been removed.
 */
const UiManagementPage: React.FC = () => {
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
            // --- FIX: Explicitly type 'd' as DownloadStatus ---
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
        // --- FIX: Explicitly type 'ui' as AvailableUiItem ---
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

    // --- Action Handlers (Logic now lives here) ---

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

    // --- Render Logic ---

    if (isLoading && combinedUiData.length === 0) {
        return (
            <div className="page-state-container">
                <Loader2 size={32} className="animate-spin" />
                <p>Loading UI Environments...</p>
            </div>
        );
    }

    return (
        <>
            <div className="ui-management-page">
                <div className="config-header">
                    <div className="config-header-text">
                        <h1>UI Environments</h1>
                        <p>Install, run, and manage supported AI user interfaces.</p>
                    </div>
                    <button className="button" onClick={() => setIsAdoptModalOpen(true)}>
                        <ClipboardCheck size={18} /> Adopt Existing UI
                    </button>
                </div>

                <div className="ui-management-grid">
                    {combinedUiData.map((ui) => {
                        const busy = isUiBusy(ui.ui_name);
                        return (
                            <div key={ui.ui_name} className="config-card ui-card">
                                <h2 className="config-card-header">
                                    <Layers size={20} />
                                    {ui.ui_name}
                                </h2>
                                <div className="config-card-body">
                                    <div className="ui-status-section">
                                        <div
                                            className={`status-badge ${
                                                ui.is_installed ? 'installed' : 'not-installed'
                                            }`}
                                        >
                                            {ui.is_installed ? (
                                                <>
                                                    <CheckCircle size={14} /> Installed
                                                </>
                                            ) : (
                                                'Not Installed'
                                            )}
                                        </div>
                                        {ui.is_installed && (
                                            <div
                                                className={`status-badge ${
                                                    ui.is_running ? 'running' : 'stopped'
                                                }`}
                                            >
                                                {ui.is_running ? (
                                                    <>
                                                        <Loader2
                                                            size={14}
                                                            className="animate-spin"
                                                        />{' '}
                                                        Running
                                                    </>
                                                ) : (
                                                    'Stopped'
                                                )}
                                            </div>
                                        )}
                                    </div>
                                    <p className="ui-git-url" title={ui.git_url}>
                                        {ui.git_url}
                                    </p>
                                    {ui.install_path && (
                                        <p className="ui-install-path" title={ui.install_path}>
                                            Path: {ui.install_path}
                                        </p>
                                    )}
                                </div>
                                <div className="modal-actions ui-card-actions">
                                    {!ui.is_installed ? (
                                        <button
                                            className="button button-primary full-width"
                                            onClick={() => openInstallModal(ui)}
                                            disabled={busy}
                                        >
                                            <Download size={18} /> Install
                                        </button>
                                    ) : (
                                        <>
                                            <button
                                                className="button button-danger"
                                                onClick={() => requestDelete(ui.ui_name)}
                                                title="Delete the managed installation."
                                            >
                                                <Trash2 size={18} />
                                            </button>
                                            {ui.is_running && ui.running_task_id ? (
                                                <button
                                                    className="button button-warning"
                                                    onClick={() => handleStop(ui.running_task_id!)}
                                                    disabled={busy}
                                                >
                                                    <StopCircle size={18} /> Stop
                                                </button>
                                            ) : (
                                                <button
                                                    className="button button-success"
                                                    onClick={() => handleRun(ui.ui_name)}
                                                    disabled={busy}
                                                >
                                                    <Play size={18} /> Start
                                                </button>
                                            )}
                                        </>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* --- Modals --- */}
            <InstallUiModal
                isOpen={isInstallModalOpen}
                onClose={() => setIsInstallModalOpen(false)}
                uiToInstall={uiToInstall}
                onConfirmInstall={handleInstall}
                isSubmitting={
                    !!uiToInstall &&
                    isUiBusy(uiToInstall.ui_name) &&
                    !uiStatuses.find((s) => s.ui_name === uiToInstall.ui_name)?.is_installed
                }
            />
            <AdoptUiModal
                isOpen={isAdoptModalOpen}
                onClose={() => setIsAdoptModalOpen(false)}
                availableUis={availableUis}
                onConfirmRepair={handleRepair}
                onConfirmFinalize={handleFinalizeAdoption}
            />
            <ConfirmModal
                isOpen={isDeleteConfirmOpen}
                title={`Delete ${uiToDelete}?`}
                message={`Are you sure you want to permanently delete the installation for ${uiToDelete}? This action cannot be undone.`}
                onConfirm={handleDelete}
                onCancel={() => setIsDeleteConfirmOpen(false)}
                confirmText="Yes, Delete"
                isDanger={true}
            />
        </>
    );
};

export default UiManagementPage;

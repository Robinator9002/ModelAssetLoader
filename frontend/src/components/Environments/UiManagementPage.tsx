// frontend/src/components/Environments/UiManagementPage.tsx
import React, { useState } from 'react';
import {
    // Type definitions
    type AvailableUiItem,
    type ManagedUiStatus,
    type UiNameType,
    type UiInstallRequest,
} from '../../api/api';
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
import AdoptUiModal from './AdoptUiModal'; // Import the new adoption modal

/**
 * Props for the UiManagementPage component.
 * Updated to include handlers for the adoption workflow.
 */
interface UiManagementPageProps {
    availableUis: AvailableUiItem[];
    uiStatuses: ManagedUiStatus[];
    onInstall: (request: UiInstallRequest) => void;
    onRun: (uiName: UiNameType) => void;
    onStop: (taskId: string) => void;
    onDelete: (uiName: UiNameType) => void;
    isBusy: (uiName: UiNameType) => boolean;
    // Handlers for the adoption process, to be passed from App.tsx
    onRepair: (uiName: UiNameType, path: string, issues: string[]) => void;
    onFinalizeAdoption: (uiName: UiNameType, path: string) => void;
}

/**
 * A dedicated page for discovering, installing, and managing different AI UI environments.
 */
const UiManagementPage: React.FC<UiManagementPageProps> = ({
    availableUis,
    uiStatuses,
    onInstall,
    onRun,
    onStop,
    onDelete,
    isBusy,
    onRepair,
    onFinalizeAdoption,
}) => {
    // --- State for Modals ---
    const [isInstallModalOpen, setIsInstallModalOpen] = useState(false);
    const [uiToInstall, setUiToInstall] = useState<AvailableUiItem | null>(null);
    const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
    const [uiToDelete, setUiToDelete] = useState<UiNameType | null>(null);
    // State for the new adoption modal
    const [isAdoptModalOpen, setIsAdoptModalOpen] = useState(false);

    // --- Modal Handlers ---
    const handleOpenInstallModal = (ui: AvailableUiItem) => {
        setUiToInstall(ui);
        setIsInstallModalOpen(true);
    };

    const handleCloseInstallModal = () => {
        setUiToInstall(null);
        setIsInstallModalOpen(false);
    };

    const handleConfirmInstall = (request: UiInstallRequest) => {
        onInstall(request);
        handleCloseInstallModal();
    };

    const handleRequestDelete = (uiName: UiNameType) => {
        setUiToDelete(uiName);
        setIsDeleteConfirmOpen(true);
    };

    const handleConfirmDelete = () => {
        if (uiToDelete) {
            onDelete(uiToDelete);
        }
        setIsDeleteConfirmOpen(false);
        setUiToDelete(null);
    };

    // --- Data Combination Logic ---
    const getCombinedUiData = () => {
        const statusMap = new Map(uiStatuses.map((s) => [s.ui_name, s]));
        return availableUis.map((ui) => {
            const status = statusMap.get(ui.ui_name);
            return {
                ...ui,
                is_installed: status?.is_installed ?? false,
                is_running: status?.is_running ?? false,
                install_path: status?.install_path,
                running_task_id: status?.running_task_id,
            };
        });
    };

    const combinedUiData = getCombinedUiData();

    return (
        <>
            <div className="ui-management-page">
                <div className="config-header">
                    <div className="config-header-text">
                        <h1>UI Environments</h1>
                        <p>Install, run, and manage supported AI user interfaces.</p>
                    </div>
                    {/* Button to trigger the new adoption modal */}
                    <button className="button" onClick={() => setIsAdoptModalOpen(true)}>
                        <ClipboardCheck size={18} /> Adopt Existing UI
                    </button>
                </div>

                <div className="ui-management-grid">
                    {combinedUiData.map((ui) => {
                        const isUiBusy = isBusy(ui.ui_name);

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
                                            onClick={() => handleOpenInstallModal(ui)}
                                            disabled={isUiBusy}
                                        >
                                            <Download size={18} /> Install
                                        </button>
                                    ) : (
                                        <>
                                            <button
                                                className="button button-danger"
                                                onClick={() => handleRequestDelete(ui.ui_name)}
                                                title="Delete the managed installation."
                                            >
                                                <Trash2 size={18} />
                                            </button>
                                            {ui.is_running && ui.running_task_id ? (
                                                <button
                                                    className="button button-warning"
                                                    onClick={() => onStop(ui.running_task_id!)}
                                                    disabled={isUiBusy}
                                                >
                                                    <StopCircle size={18} /> Stop
                                                </button>
                                            ) : (
                                                <button
                                                    className="button button-success"
                                                    onClick={() => onRun(ui.ui_name)}
                                                    disabled={isUiBusy}
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

            {/* Render the modals */}
            <InstallUiModal
                isOpen={isInstallModalOpen}
                onClose={handleCloseInstallModal}
                uiToInstall={uiToInstall}
                onConfirmInstall={handleConfirmInstall}
                isSubmitting={
                    !!uiToInstall &&
                    isBusy(uiToInstall.ui_name) &&
                    !uiStatuses.find((s) => s.ui_name === uiToInstall.ui_name)?.is_installed
                }
            />
            <AdoptUiModal
                isOpen={isAdoptModalOpen}
                onClose={() => setIsAdoptModalOpen(false)}
                availableUis={availableUis}
                onConfirmRepair={onRepair}
                onConfirmFinalize={onFinalizeAdoption}
            />
            <ConfirmModal
                isOpen={isDeleteConfirmOpen}
                title={`Delete ${uiToDelete}?`}
                message={`Are you sure you want to permanently delete the installation for ${uiToDelete}? This action cannot be undone.`}
                onConfirm={handleConfirmDelete}
                onCancel={() => setIsDeleteConfirmOpen(false)}
                confirmText="Yes, Delete"
                isDanger={true}
            />
        </>
    );
};

export default UiManagementPage;

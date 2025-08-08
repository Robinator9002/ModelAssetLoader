// frontend/src/components/Environments/UiManagementPage.tsx
import React from 'react';
import { useUiManagement } from '../../hooks/useUiManagement';
import {
    Layers,
    Download,
    Trash2,
    Play,
    CheckCircle,
    Loader2,
    StopCircle,
    ClipboardCheck,
    Package,
    Edit, // --- NEW: Import the Edit icon ---
} from 'lucide-react';
import InstallUiModal from './InstallUiModal';
import ConfirmModal from '../Layout/ConfirmModal';
import AdoptUiModal from './AdoptUiModal';
import EditUiModal from './EditUiModal'; // --- NEW: Import the EditUiModal component ---

const UiManagementPage: React.FC = () => {
    const {
        isLoading,
        installedUis,
        availableUis,
        activeTasks,
        isInstallModalOpen,
        uiToInstall,
        isDeleteConfirmOpen,
        uiToDelete,
        isAdoptModalOpen,
        isEditModalOpen, // --- NEW: Destructure edit modal state ---
        uiToEdit, // --- NEW: Destructure edit modal state ---
        isUiBusy,
        handleInstall,
        handleRun,
        handleStop,
        handleDelete,
        handleRepair,
        handleFinalizeAdoption,
        handleUpdateSuccess, // --- NEW: Destructure update handler ---
        openInstallModal,
        requestDelete,
        openEditModal, // --- NEW: Destructure modal opener ---
        setIsInstallModalOpen,
        setIsDeleteConfirmOpen,
        setUiToDelete,
        setIsAdoptModalOpen,
        closeEditModal, // --- NEW: Destructure modal closer ---
    } = useUiManagement();

    if (isLoading && installedUis.length === 0) {
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
                        <p>Install, run, and manage your unique AI user interface instances.</p>
                    </div>
                    <button className="button" onClick={() => setIsAdoptModalOpen(true)}>
                        <ClipboardCheck size={18} /> Adopt Existing UI
                    </button>
                </div>

                <h2 className="ui-section-header">Installed Instances</h2>
                <div className="ui-management-grid">
                    {installedUis.map((ui) => {
                        const busy = isUiBusy(ui.installation_id);
                        return (
                            <div key={ui.installation_id} className="config-card ui-card">
                                <h2 className="config-card-header">
                                    <Layers size={20} />
                                    {ui.display_name}
                                </h2>
                                <div className="config-card-body">
                                    <div className="ui-status-section">
                                        <div className="status-badge installed">
                                            <CheckCircle size={14} /> Installed
                                        </div>
                                        <div
                                            className={`status-badge ${
                                                ui.is_running ? 'running' : 'stopped'
                                            }`}
                                        >
                                            {ui.is_running ? (
                                                <>
                                                    <Loader2 size={14} className="animate-spin" />{' '}
                                                    Running
                                                </>
                                            ) : (
                                                'Stopped'
                                            )}
                                        </div>
                                        <div className="status-badge type-badge">{ui.ui_name}</div>
                                    </div>
                                    <p className="ui-install-path" title={ui.install_path || ''}>
                                        Path: {ui.install_path}
                                    </p>
                                </div>
                                <div className="modal-actions ui-card-actions">
                                    <button
                                        className="button button-danger"
                                        onClick={() => requestDelete(ui)}
                                        title="Delete this instance."
                                        disabled={busy}
                                    >
                                        <Trash2 size={18} />
                                    </button>
                                    {/* --- NEW: Add the Edit button --- */}
                                    <button
                                        className="button"
                                        onClick={() => openEditModal(ui)}
                                        title="Edit this instance."
                                        disabled={busy}
                                    >
                                        <Edit size={18} />
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
                                            onClick={() => handleRun(ui.installation_id)}
                                            disabled={busy}
                                        >
                                            <Play size={18} /> Start
                                        </button>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>

                <h2 className="ui-section-header">Available to Install</h2>
                <div className="ui-management-grid">
                    {availableUis.map((ui) => (
                        <div key={ui.ui_name} className="config-card ui-card available">
                            <h2 className="config-card-header">
                                <Package size={20} />
                                {ui.ui_name}
                            </h2>
                            <div className="config-card-body">
                                <p className="ui-git-url" title={ui.git_url}>
                                    Source: {ui.git_url}
                                </p>
                            </div>
                            <div className="modal-actions ui-card-actions">
                                <button
                                    className="button button-primary full-width"
                                    onClick={() => openInstallModal(ui)}
                                >
                                    <Download size={18} /> Install New Instance...
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* --- Modals --- */}
            <InstallUiModal
                isOpen={isInstallModalOpen}
                onClose={() => setIsInstallModalOpen(false)}
                uiToInstall={uiToInstall}
                onConfirmInstall={handleInstall}
                isSubmitting={!!uiToInstall && activeTasks.size > 0}
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
                title={`Delete ${uiToDelete?.display_name}?`}
                message={`Are you sure you want to permanently delete the '${uiToDelete?.display_name}' instance? This action cannot be undone.`}
                onConfirm={handleDelete}
                onCancel={() => {
                    setIsDeleteConfirmOpen(false);
                    setUiToDelete(null);
                }}
                confirmText="Yes, Delete"
                isDanger={true}
            />
            {/* --- NEW: Render the EditUiModal --- */}
            <EditUiModal
                isOpen={isEditModalOpen}
                onClose={closeEditModal}
                uiToEdit={uiToEdit}
                onUpdateSuccess={handleUpdateSuccess}
            />
        </>
    );
};

export default UiManagementPage;

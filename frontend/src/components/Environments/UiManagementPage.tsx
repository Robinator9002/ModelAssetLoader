// frontend/src/components/Environments/UiManagementPage.tsx
import React from 'react';
import { useUiManagement } from './useUiManagement';
import {
    Layers,
    Download,
    Trash2,
    Play,
    CheckCircle,
    Loader2,
    StopCircle,
    ClipboardCheck,
    Package, // --- NEW: Icon for available UIs ---
} from 'lucide-react';
import InstallUiModal from './InstallUiModal';
import ConfirmModal from '../Layout/ConfirmModal';
import AdoptUiModal from './AdoptUiModal';

/**
 * @refactor This component has been completely refactored to render a list of
 * unique UI instances, rather than a combined list of UI types. It now has two
 * distinct sections: one for managing installed instances and another for installing
 * new UIs from the list of available types. All actions are now correctly

 * wired up to use the unique `installation_id`.
 */
const UiManagementPage: React.FC = () => {
    const {
        isLoading,
        installedUis, // --- REFACTOR: Use the direct list of installed instances ---
        availableUis,
        isInstallModalOpen,
        uiToInstall,
        isDeleteConfirmOpen,
        uiToDelete,
        isAdoptModalOpen,
        isUiBusy,
        handleInstall,
        handleRun,
        handleStop,
        handleDelete,
        handleRepair,
        handleFinalizeAdoption,
        openInstallModal,
        requestDelete,
        setIsInstallModalOpen,
        setIsDeleteConfirmOpen,
        setUiToDelete,
        setIsAdoptModalOpen,
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

                {/* --- Section for Installed Instances --- */}
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
                                        onClick={() => requestDelete(ui)} // --- FIX: Pass the full ui object ---
                                        title="Delete this instance."
                                        disabled={busy}
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
                                            onClick={() => handleRun(ui.installation_id)} // --- FIX: Pass installation_id ---
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

                {/* --- Section for Available UIs to Install --- */}
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
                isSubmitting={!!uiToInstall && activeTasks.size > 0} // Simplified busy check for install
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
                // --- FIX: Use the display_name from the uiToDelete object ---
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
        </>
    );
};

export default UiManagementPage;

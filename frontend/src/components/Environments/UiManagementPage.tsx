// frontend/src/components/Environments/UiManagementPage.tsx
import React from 'react';
// --- REFACTOR: Import the new custom hook ---
import { useUiManagement } from './useUiManagement';

// --- Component & Icon Imports ---
import {
    Layers,
    Download,
    Trash2,
    Play,
    CheckCircle,
    Loader2,
    StopCircle,
    ClipboardCheck,
} from 'lucide-react';
import InstallUiModal from './InstallUiModal';
import ConfirmModal from '../Layout/ConfirmModal';
import AdoptUiModal from './AdoptUiModal';

/**
 * @refactor This component has been completely refactored to be a "presentational"
 * or "dumb" component. All of its complex state management, data fetching, and
 * event handling logic has been extracted into the `useUiManagement` custom hook.
 *
 * The component's sole responsibility is now to render the UI based on the state
 * and functions provided by the hook. This makes the component significantly
 * cleaner, easier to read, and focused only on the view layer.
 */
const UiManagementPage: React.FC = () => {
    // --- REFACTOR: All logic is now encapsulated in this single hook call ---
    const {
        isLoading,
        combinedUiData,
        isInstallModalOpen,
        uiToInstall,
        isDeleteConfirmOpen,
        uiToDelete,
        isAdoptModalOpen,
        availableUis,
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
                isSubmitting={!!uiToInstall && isUiBusy(uiToInstall.ui_name)}
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

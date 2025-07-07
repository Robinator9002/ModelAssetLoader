// frontend/src/components/Environments/UiManagementPage.tsx
import React from 'react';
import { type AvailableUiItem, type ManagedUiStatus, type UiNameType } from '../../api/api';
import { Layers, Download, Settings, Play, CheckCircle, Loader2, FolderPlus } from 'lucide-react';

/**
 * Props for the UiManagementPage component.
 */
interface UiManagementPageProps {
    availableUis: AvailableUiItem[];
    uiStatuses: ManagedUiStatus[];
    onInstall: (uiName: UiNameType) => void;
    onRun: (uiName: UiNameType) => void;
    onStop: (taskId: string) => void;
    onDelete: (uiName: UiNameType) => void;
    isBusy: (uiName: UiNameType) => boolean;
    // --- PHASE 3: NEW PROP ---
    onAdopt: (uiName: UiNameType) => void;
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
    onAdopt, // --- PHASE 3: NEW PROP ---
}) => {
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
        <div className="ui-management-page">
            <div className="config-header">
                <h1>UI Environment Management</h1>
                <p>Install, run, and manage supported AI user interfaces.</p>
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
                                                    <Loader2 size={14} className="animate-spin" />{' '}
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
                                    // --- PHASE 3: MODIFIED BUTTONS ---
                                    <>
                                        <button
                                            className="button button-secondary"
                                            onClick={() => onAdopt(ui.ui_name)}
                                            disabled={isUiBusy}
                                        >
                                            <FolderPlus size={18} /> Adopt Existing
                                        </button>
                                        <button
                                            className="button button-primary"
                                            onClick={() => onInstall(ui.ui_name)}
                                            disabled={isUiBusy}
                                        >
                                            <Download size={18} /> Clean Install
                                        </button>
                                    </>
                                ) : (
                                    <>
                                        <button
                                            className="button"
                                            onClick={() => onDelete(ui.ui_name)}
                                            title="This will un-adopt an existing installation or delete a managed one."
                                        >
                                            <Settings size={18} /> Manage
                                        </button>
                                        {ui.is_running && ui.running_task_id ? (
                                            <button
                                                className="button button-danger"
                                                onClick={() => onStop(ui.running_task_id!)}
                                                disabled={isUiBusy}
                                            >
                                                <Play
                                                    size={18}
                                                    style={{ transform: 'rotate(180deg)' }}
                                                />{' '}
                                                Stop
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
    );
};

export default UiManagementPage;

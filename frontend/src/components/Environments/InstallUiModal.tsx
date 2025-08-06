// frontend/src/components/Environments/InstallUiModal.tsx
import React, { useState, useEffect } from 'react';
import { type AvailableUiItem, type UiInstallRequest } from '~/api';
import { X, Folder, Download, Loader2, Package, Edit, DownloadCloud } from 'lucide-react';
import FolderSelector from '../Files/FolderSelector';

interface InstallUiModalProps {
    isOpen: boolean;
    onClose: () => void;
    uiToInstall: AvailableUiItem | null;
    onConfirmInstall: (installRequest: UiInstallRequest) => void;
    isSubmitting: boolean;
}

const InstallUiModal: React.FC<InstallUiModalProps> = ({
    isOpen,
    onClose,
    uiToInstall,
    onConfirmInstall,
    isSubmitting,
}) => {
    // --- Component State ---
    const [installType, setInstallType] = useState<'default' | 'custom'>('default');
    const [customInstallPath, setCustomInstallPath] = useState<string>('');
    const [setAsActive, setSetAsActive] = useState<boolean>(true);
    const [isFolderSelectorOpen, setIsFolderSelectorOpen] = useState<boolean>(false);

    // Reset state when the modal is opened for a new UI
    useEffect(() => {
        if (isOpen) {
            setInstallType('default');
            setCustomInstallPath('');
            setSetAsActive(true);
        }
    }, [isOpen]);

    // --- Event Handlers ---
    const handleConfirm = () => {
        if (!uiToInstall) return;

        const request: UiInstallRequest = {
            ui_name: uiToInstall.ui_name,
            custom_install_path: installType === 'custom' ? customInstallPath.trim() || null : null,
            set_as_active: setAsActive,
        };
        onConfirmInstall(request);
    };

    const handleSelectPath = (path: string) => {
        // Append the UI name to the selected path for a sensible default
        const finalPath = path ? `${path}/${uiToInstall?.ui_name || ''}` : '';
        setCustomInstallPath(finalPath);
        setIsFolderSelectorOpen(false);
    };

    if (!isOpen || !uiToInstall) {
        return null;
    }

    return (
        <>
            <div className="modal-overlay active">
                <div
                    className="modal-content install-modal-content"
                    onClick={(e) => e.stopPropagation()}
                >
                    <div className="modal-header">
                        <div className="modal-header-content">
                            <Package size={22} className="header-icon" />
                            <h3>Install {uiToInstall.ui_name}</h3>
                        </div>
                        <button
                            onClick={onClose}
                            className="button-icon close-button"
                            aria-label="Close"
                            disabled={isSubmitting}
                        >
                            <X size={20} />
                        </button>
                    </div>
                    <div className="modal-body install-modal-body">
                        <p className="modal-description">
                            Choose an installation method for <strong>{uiToInstall.ui_name}</strong>
                            .
                        </p>

                        <div className="install-option-cards">
                            {/* Default Install Card */}
                            <div
                                className={`install-option-card ${
                                    installType === 'default' ? 'selected' : ''
                                }`}
                                onClick={() => !isSubmitting && setInstallType('default')}
                                tabIndex={isSubmitting ? -1 : 0}
                                onKeyDown={(e) =>
                                    !isSubmitting && e.key === 'Enter' && setInstallType('default')
                                }
                                role="radio"
                                aria-checked={installType === 'default'}
                            >
                                <DownloadCloud size={28} className="option-card-icon" />
                                <div className="option-card-text">
                                    <h4 className="config-label">Default Install</h4>
                                    <p className="config-hint">
                                        Install into the M.A.L. managed folder. Recommended.
                                    </p>
                                </div>
                            </div>

                            {/* Custom Install Card */}
                            <div
                                className={`install-option-card ${
                                    installType === 'custom' ? 'selected' : ''
                                }`}
                                onClick={() => !isSubmitting && setInstallType('custom')}
                                tabIndex={isSubmitting ? -1 : 0}
                                onKeyDown={(e) =>
                                    !isSubmitting && e.key === 'Enter' && setInstallType('custom')
                                }
                                role="radio"
                                aria-checked={installType === 'custom'}
                            >
                                <Edit size={28} className="option-card-icon" />
                                <div className="option-card-text">
                                    <h4 className="config-label">Custom Location</h4>
                                    <p className="config-hint">
                                        Choose a specific folder for the installation.
                                    </p>
                                </div>
                            </div>
                        </div>

                        {/* Custom Path Input - shown conditionally */}
                        {installType === 'custom' && (
                            <div className="form-section custom-path-section">
                                <label htmlFor="installPath" className="config-label">
                                    Custom Installation Path
                                </label>
                                <div className="base-path-selector">
                                    <input
                                        type="text"
                                        id="installPath"
                                        value={customInstallPath}
                                        onChange={(e) => setCustomInstallPath(e.target.value)}
                                        placeholder="e.g., /path/to/my/uis/ComfyUI"
                                        className="config-input path-input"
                                        disabled={isSubmitting}
                                    />
                                    <button
                                        onClick={() => setIsFolderSelectorOpen(true)}
                                        className="button"
                                        disabled={isSubmitting}
                                    >
                                        <Folder size={16} /> Browse...
                                    </button>
                                </div>
                            </div>
                        )}

                        {/* Set as Active Section */}
                        <div className="form-section set-active-section">
                            <label className="toggle-switch">
                                <input
                                    type="checkbox"
                                    checked={setAsActive}
                                    onChange={() => setSetAsActive(!setAsActive)}
                                    disabled={isSubmitting}
                                />
                                <span className="slider"></span>
                            </label>
                            <div
                                className="toggle-label-group"
                                onClick={() => setSetAsActive(!setAsActive)}
                            >
                                <span className="config-label">Set as active configuration</span>
                                <p className="config-hint">
                                    Use this UI in 'Automatic' mode after installation.
                                </p>
                            </div>
                        </div>
                    </div>
                    <div className="modal-actions">
                        <button onClick={onClose} className="button" disabled={isSubmitting}>
                            Cancel
                        </button>
                        <button
                            onClick={handleConfirm}
                            className="button button-primary"
                            disabled={isSubmitting}
                        >
                            {isSubmitting ? (
                                <Loader2 size={18} className="animate-spin" />
                            ) : (
                                <Download size={18} />
                            )}
                            {isSubmitting ? 'Starting...' : 'Start Installation'}
                        </button>
                    </div>
                </div>
            </div>
            <FolderSelector
                isOpen={isFolderSelectorOpen}
                onSelectFinalPath={handleSelectPath}
                onCancel={() => setIsFolderSelectorOpen(false)}
            />
        </>
    );
};

export default InstallUiModal;

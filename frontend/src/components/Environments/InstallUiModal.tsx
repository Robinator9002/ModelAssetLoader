// frontend/src/components/Environments/InstallUiModal.tsx
import React, { useState, useEffect } from 'react';
import { type AvailableUiItem, type UiInstallRequest } from '../../api/api';
import { X, Folder, Download, Loader2, CheckSquare, Square } from 'lucide-react';
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
    const [customInstallPath, setCustomInstallPath] = useState<string>('');
    const [setAsActive, setSetAsActive] = useState<boolean>(true);
    const [isFolderSelectorOpen, setIsFolderSelectorOpen] = useState<boolean>(false);

    // Reset state when the modal is opened for a new UI
    useEffect(() => {
        if (isOpen) {
            setCustomInstallPath('');
            setSetAsActive(true);
        }
    }, [isOpen]);

    // --- Event Handlers ---
    const handleConfirm = () => {
        if (!uiToInstall) return;

        const request: UiInstallRequest = {
            ui_name: uiToInstall.ui_name,
            custom_install_path: customInstallPath.trim() || null,
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
                <div className="modal-content" onClick={(e) => e.stopPropagation()}>
                    <div className="modal-header">
                        <h3>Install {uiToInstall.ui_name}</h3>
                        <button
                            onClick={onClose}
                            className="button-icon close-button"
                            aria-label="Close"
                            disabled={isSubmitting}
                        >
                            <X size={20} />
                        </button>
                    </div>
                    <div className="modal-body">
                        <p className="modal-description">
                            Configure the installation options for{' '}
                            <strong>{uiToInstall.ui_name}</strong>.
                        </p>

                        {/* Installation Path Section */}
                        <div className="form-section">
                            <label htmlFor="installPath" className="config-label">
                                Installation Path (Optional)
                            </label>
                            <p className="config-hint">
                                Leave blank to install to the default M.A.L. managed folder.
                            </p>
                            <div className="base-path-selector">
                                <input
                                    type="text"
                                    id="installPath"
                                    value={customInstallPath}
                                    onChange={(e) => setCustomInstallPath(e.target.value)}
                                    placeholder="Default managed folder..."
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

                        {/* Set as Active Section */}
                        <div className="form-section">
                            <div
                                className="checkbox-container"
                                onClick={() => setSetAsActive(!setAsActive)}
                                onKeyDown={(e) => {
                                    if (e.key === ' ' || e.key === 'Enter') {
                                        setSetAsActive(!setAsActive);
                                    }
                                }}
                                tabIndex={0}
                                role="checkbox"
                                aria-checked={setAsActive}
                            >
                                {setAsActive ? (
                                    <CheckSquare size={20} className="checkbox-icon checked" />
                                ) : (
                                    <Square size={20} className="checkbox-icon" />
                                )}
                                <label
                                    htmlFor="setAsActive"
                                    className="config-label"
                                    onClick={(e) => e.preventDefault()} // Prevent double toggle
                                >
                                    Set as active configuration after installation
                                </label>
                            </div>
                            <p className="config-hint">
                                This will automatically select the UI in the settings page in
                                'Automatic' mode upon successful installation.
                            </p>
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

// frontend/src/components/Environments/InstallUiModal.tsx
import React, { useState, useEffect } from 'react';
import { type AvailableUiItem, type UiInstallRequest } from '~/api';
import {
    X,
    Folder,
    Download,
    Loader2,
    Package,
    Edit,
    DownloadCloud,
    CaseSensitive,
} from 'lucide-react';
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
    // --- NEW: Add state for the user-provided display name ---
    const [displayName, setDisplayName] = useState<string>('');
    const [installType, setInstallType] = useState<'default' | 'custom'>('default');
    const [customInstallPath, setCustomInstallPath] = useState<string>('');
    const [setAsActive, setSetAsActive] = useState<boolean>(true);
    const [isFolderSelectorOpen, setIsFolderSelectorOpen] = useState<boolean>(false);

    // Reset state when the modal is opened for a new UI
    useEffect(() => {
        if (isOpen && uiToInstall) {
            // --- REFACTOR: Set a default display name when the modal opens ---
            setDisplayName(uiToInstall.ui_name);
            setInstallType('default');
            setCustomInstallPath('');
            setSetAsActive(true);
        }
    }, [isOpen, uiToInstall]);

    // --- Event Handlers ---
    const handleConfirm = () => {
        if (!uiToInstall || !displayName.trim()) return;

        // --- REFACTOR: Include the new display_name in the request payload ---
        const request: UiInstallRequest = {
            ui_name: uiToInstall.ui_name,
            display_name: displayName.trim(),
            custom_install_path: installType === 'custom' ? customInstallPath.trim() || null : null,
            set_as_active: setAsActive,
        };
        onConfirmInstall(request);
    };

    const handleSelectPath = (path: string) => {
        const finalPath = path ? `${path}/${displayName.trim() || uiToInstall?.ui_name || ''}` : '';
        setCustomInstallPath(finalPath);
        setIsFolderSelectorOpen(false);
    };

    if (!isOpen || !uiToInstall) {
        return null;
    }

    // --- REFACTOR: Disable the confirm button if the display name is empty ---
    const isConfirmDisabled = isSubmitting || !displayName.trim();

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
                        {/* --- NEW: Display Name Input Field --- */}
                        <div className="form-section">
                            <label htmlFor="displayName" className="config-label">
                                Instance Name
                            </label>
                            <div className="input-with-icon">
                                <CaseSensitive size={18} className="input-icon" />
                                <input
                                    type="text"
                                    id="displayName"
                                    value={displayName}
                                    onChange={(e) => setDisplayName(e.target.value)}
                                    placeholder="e.g., ComfyUI - SDXL"
                                    className="config-input"
                                    disabled={isSubmitting}
                                />
                            </div>
                            <p className="config-hint">
                                Give this installation a unique, memorable name.
                            </p>
                        </div>

                        <div className="install-option-cards">
                            {/* Default Install Card */}
                            <div
                                className={`install-option-card ${
                                    installType === 'default' ? 'selected' : ''
                                }`}
                                onClick={() => !isSubmitting && setInstallType('default')}
                                tabIndex={isSubmitting ? -1 : 0}
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
                            disabled={isConfirmDisabled}
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

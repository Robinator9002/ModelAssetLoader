// frontend/src/components/Environments/EditUiModal.tsx
import React, { useState, useEffect } from 'react';
import { type ManagedUiStatus, updateUiInstanceAPI } from '~/api';
import { X, Save, Folder, AlertTriangle, Loader2 } from 'lucide-react';
import FolderSelector from '../Files/FolderSelector';

interface EditUiModalProps {
    isOpen: boolean;
    onClose: () => void;
    uiToEdit: ManagedUiStatus | null;
    onUpdateSuccess: () => void;
}

const EditUiModal: React.FC<EditUiModalProps> = ({
    isOpen,
    onClose,
    uiToEdit,
    onUpdateSuccess,
}) => {
    const [displayName, setDisplayName] = useState('');
    const [installPath, setInstallPath] = useState('');
    const [isFolderSelectorOpen, setFolderSelectorOpen] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (uiToEdit) {
            setDisplayName(uiToEdit.display_name);
            setInstallPath(uiToEdit.install_path || '');
            setError(null);
            setIsSubmitting(false);
        }
    }, [uiToEdit]);

    const handleSaveChanges = async () => {
        if (!uiToEdit) return;

        const originalName = uiToEdit.display_name;
        const originalPath = uiToEdit.install_path || '';

        // Determine what has changed
        const nameChanged = displayName.trim() !== originalName;
        const pathChanged = installPath.trim() !== originalPath;

        if (!displayName.trim()) {
            setError('Display name cannot be empty.');
            return;
        }

        if (!nameChanged && !pathChanged) {
            setError('No changes were made.');
            return;
        }

        setIsSubmitting(true);
        setError(null);

        try {
            await updateUiInstanceAPI(uiToEdit.installation_id, {
                display_name: nameChanged ? displayName.trim() : undefined,
                path: pathChanged ? installPath.trim() : undefined,
            });
            onUpdateSuccess();
        } catch (err: any) {
            setError(err.message || 'An unknown error occurred.');
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleSelectPath = (path: string) => {
        setInstallPath(path);
        setFolderSelectorOpen(false);
    };

    if (!isOpen || !uiToEdit) {
        return null;
    }

    return (
        <>
            <div className={`modal-overlay ${isOpen ? 'active' : ''}`}>
                <div className="modal-content">
                    <div className="modal-header">
                        <h3>Edit '{uiToEdit.display_name}'</h3>
                        <button onClick={onClose} className="button-icon close-button">
                            <X size={20} />
                        </button>
                    </div>
                    <div className="modal-body">
                        {error && (
                            <div className="modal-error-banner">
                                <AlertTriangle size={16} />
                                <span>{error}</span>
                            </div>
                        )}
                        <div className="form-group">
                            <label htmlFor="displayName">Display Name</label>
                            <input
                                id="displayName"
                                type="text"
                                value={displayName}
                                onChange={(e) => setDisplayName(e.target.value)}
                                placeholder="e.g., ComfyUI - Main"
                                disabled={isSubmitting}
                            />
                        </div>
                        <div className="form-group">
                            <label htmlFor="installPath">Installation Path</label>
                            <div className="input-with-button">
                                <input
                                    id="installPath"
                                    type="text"
                                    value={installPath}
                                    onChange={(e) => setInstallPath(e.target.value)}
                                    placeholder="e.g., C:\\Users\\You\\ComfyUI"
                                    disabled={isSubmitting}
                                />
                                <button
                                    className="button-icon"
                                    onClick={() => setFolderSelectorOpen(true)}
                                    title="Select a folder"
                                    disabled={isSubmitting}
                                >
                                    <Folder size={18} />
                                </button>
                            </div>
                        </div>
                    </div>
                    <div className="modal-actions">
                        <button className="button" onClick={onClose} disabled={isSubmitting}>
                            Cancel
                        </button>
                        <button
                            className="button button-primary"
                            onClick={handleSaveChanges}
                            disabled={isSubmitting}
                        >
                            {isSubmitting ? (
                                <Loader2 size={18} className="animate-spin" />
                            ) : (
                                <Save size={18} />
                            )}
                            Save Changes
                        </button>
                    </div>
                </div>
            </div>
            <FolderSelector
                isOpen={isFolderSelectorOpen}
                onSelectFinalPath={handleSelectPath}
                onCancel={() => setFolderSelectorOpen(false)}
            />
        </>
    );
};

export default EditUiModal;

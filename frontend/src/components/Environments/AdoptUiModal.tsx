// frontend/src/components/Environments/AdoptUiModal.tsx
import React, { useState, useEffect, useCallback } from 'react';
import {
    type UiNameType,
    validateUiPathAPI,
    adoptUiAPI,
    type UiPathValidationResponse,
} from '../../api/api';
import FolderSelector from '../Files/FolderSelector';
import {
    X,
    FolderSearch,
    Loader2,
    CheckCircle2,
    AlertTriangle,
    ShieldCheck,
    ChevronRight,
} from 'lucide-react';

interface AdoptUiModalProps {
    isOpen: boolean;
    uiName: UiNameType | null;
    onClose: () => void;
    onAdoptionStart: (taskId: string) => void;
}

type AdoptionStep = 'select_path' | 'confirm' | 'error';

const AdoptUiModal: React.FC<AdoptUiModalProps> = ({
    isOpen,
    uiName,
    onClose,
    onAdoptionStart,
}) => {
    const [step, setStep] = useState<AdoptionStep>('select_path');
    const [selectedPath, setSelectedPath] = useState<string | null>(null);
    const [isValidating, setIsValidating] = useState(false);
    const [isAdopting, setIsAdopting] = useState(false);
    const [validationResult, setValidationResult] = useState<UiPathValidationResponse | null>(null);
    const [shouldBackup, setShouldBackup] = useState(true);
    const [isFolderSelectorOpen, setIsFolderSelectorOpen] = useState(false);

    // Reset state when the modal is opened or closed
    useEffect(() => {
        if (isOpen) {
            setStep('select_path');
            setSelectedPath(null);
            setValidationResult(null);
            setIsValidating(false);
            setIsAdopting(false);
            setShouldBackup(true);
        }
    }, [isOpen]);

    const handleValidatePath = useCallback(async () => {
        if (!selectedPath) return;
        setIsValidating(true);
        setValidationResult(null);
        try {
            const result = await validateUiPathAPI(selectedPath);
            setValidationResult(result);
            if (result.success && result.ui_name) {
                // Check if the validated UI matches the one we're trying to adopt
                if (result.ui_name === uiName) {
                    setStep('confirm');
                } else {
                    setValidationResult({
                        success: false,
                        error: `Validation successful, but this is a '${result.ui_name}' installation, not '${uiName}'.`,
                    });
                }
            }
        } catch (e) {
            setValidationResult({
                success: false,
                error: 'An unexpected error occurred during validation.',
            });
        } finally {
            setIsValidating(false);
        }
    }, [selectedPath, uiName]);

    const handleConfirmAdoption = useCallback(async () => {
        if (!selectedPath || !validationResult?.ui_name) return;
        setIsAdopting(true);
        try {
            const response = await adoptUiAPI({
                ui_name: validationResult.ui_name,
                path: selectedPath,
                should_backup: shouldBackup,
            });
            onAdoptionStart(response.task_id);
        } catch (e: any) {
            setValidationResult({
                success: false,
                error: e.message || 'Failed to start adoption.',
            });
            setStep('error');
        } finally {
            setIsAdopting(false);
        }
    }, [selectedPath, validationResult, shouldBackup, onAdoptionStart]);

    const renderContent = () => {
        switch (step) {
            case 'select_path':
                return (
                    <>
                        <div className="modal-body">
                            <div className="adopt-icon-wrapper">
                                <FolderSearch size={48} className="icon-primary" />
                            </div>
                            <h3 className="modal-title">Adopt Existing {uiName}</h3>
                            <p className="modal-description">
                                Select the root folder of your existing '{uiName}' installation.
                            </p>
                            <div className="base-path-selector">
                                <input
                                    type="text"
                                    value={selectedPath || 'Click "Browse" to select...'}
                                    readOnly
                                    className="config-input path-input"
                                    onClick={() => setIsFolderSelectorOpen(true)}
                                />
                                <button
                                    onClick={() => setIsFolderSelectorOpen(true)}
                                    className="button"
                                >
                                    Browse...
                                </button>
                            </div>
                            {validationResult && !validationResult.success && (
                                <div className="feedback-message error">
                                    <AlertTriangle size={16} />
                                    <span>{validationResult.error}</span>
                                </div>
                            )}
                        </div>
                        <div className="modal-actions">
                            <button className="button" onClick={onClose} disabled={isValidating}>
                                Cancel
                            </button>
                            <button
                                className="button button-primary"
                                onClick={handleValidatePath}
                                disabled={!selectedPath || isValidating}
                            >
                                {isValidating ? (
                                    <Loader2 size={18} className="animate-spin" />
                                ) : (
                                    'Validate Path'
                                )}
                                <ChevronRight size={18} />
                            </button>
                        </div>
                    </>
                );
            case 'confirm':
                return (
                    <>
                        <div className="modal-body">
                            <div className="adopt-icon-wrapper">
                                <CheckCircle2 size={48} className="icon-success" />
                            </div>
                            <h3 className="modal-title">Validation Successful!</h3>
                            <p className="modal-description">
                                Ready to adopt the <strong>{validationResult?.ui_name}</strong>{' '}
                                installation located at:
                                <code className="path-display">{selectedPath}</code>
                            </p>
                            <div className="backup-option">
                                <input
                                    type="checkbox"
                                    id="backup-checkbox"
                                    checked={shouldBackup}
                                    onChange={(e) => setShouldBackup(e.target.checked)}
                                />
                                <label htmlFor="backup-checkbox">
                                    <ShieldCheck size={18} /> Create a .zip backup before proceeding
                                    (Recommended)
                                </label>
                            </div>
                        </div>
                        <div className="modal-actions">
                            <button
                                className="button"
                                onClick={() => setStep('select_path')}
                                disabled={isAdopting}
                            >
                                Back
                            </button>
                            <button
                                className="button button-success"
                                onClick={handleConfirmAdoption}
                                disabled={isAdopting}
                            >
                                {isAdopting ? (
                                    <Loader2 size={18} className="animate-spin" />
                                ) : (
                                    'Confirm & Adopt'
                                )}
                            </button>
                        </div>
                    </>
                );
            case 'error':
                return (
                    <>
                        <div className="modal-body">
                            <div className="adopt-icon-wrapper">
                                <AlertTriangle size={48} className="icon-danger" />
                            </div>
                            <h3 className="modal-title">Adoption Failed</h3>
                            <div className="feedback-message error">
                                <span>
                                    {validationResult?.error || 'An unknown error occurred.'}
                                </span>
                            </div>
                        </div>
                        <div className="modal-actions">
                            <button className="button" onClick={onClose}>
                                Close
                            </button>
                        </div>
                    </>
                );
        }
    };

    if (!isOpen) return null;

    return (
        <>
            <div className="modal-overlay adopt-modal-overlay active">
                <div className="modal-content adopt-modal-content">
                    <div className="modal-header">
                        <h4>UI Adoption Wizard</h4>
                        <button onClick={onClose} className="button-icon close-button">
                            <X size={20} />
                        </button>
                    </div>
                    {renderContent()}
                </div>
            </div>
            <FolderSelector
                isOpen={isFolderSelectorOpen}
                onSelectFinalPath={(path) => {
                    setSelectedPath(path);
                    setValidationResult(null); // Clear previous errors
                    setIsFolderSelectorOpen(false);
                }}
                onCancel={() => setIsFolderSelectorOpen(false)}
            />
        </>
    );
};

export default AdoptUiModal;

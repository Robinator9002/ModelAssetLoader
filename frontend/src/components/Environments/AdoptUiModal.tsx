// frontend/src/components/Environments/AdoptUiModal.tsx
import React, { useState, useEffect } from 'react';
import {
    analyzeUiForAdoptionAPI,
    type UiNameType,
    type AvailableUiItem,
    type AdoptionAnalysisResponse,
    type UiAdoptionAnalysisRequest,
} from '~/api';
import {
    X,
    Folder,
    ClipboardCheck,
    HeartPulse,
    Loader2,
    AlertTriangle,
    CheckCircle,
    ShieldAlert,
    CaseSensitive, // --- NEW: Import icon for the new input ---
} from 'lucide-react';
import FolderSelector from '../Files/FolderSelector';

// --- Component Props ---
interface AdoptUiModalProps {
    isOpen: boolean;
    onClose: () => void;
    availableUis: AvailableUiItem[];
    // --- REFACTOR: Callbacks now include the display_name ---
    onConfirmRepair: (
        uiName: UiNameType,
        displayName: string,
        path: string,
        issues: string[],
    ) => void;
    onConfirmFinalize: (uiName: UiNameType, displayName: string, path: string) => void;
}

// --- Helper Types ---
type ModalStep = 'initial' | 'analyzing' | 'diagnosis';

const AdoptUiModal: React.FC<AdoptUiModalProps> = ({
    isOpen,
    onClose,
    availableUis,
    onConfirmRepair,
    onConfirmFinalize,
}) => {
    // --- State Management ---
    const [step, setStep] = useState<ModalStep>('initial');
    const [selectedUiName, setSelectedUiName] = useState<UiNameType | ''>('');
    // --- NEW: Add state for the user-provided display name ---
    const [displayName, setDisplayName] = useState<string>('');
    const [selectedPath, setSelectedPath] = useState<string>('');
    const [analysisResult, setAnalysisResult] = useState<AdoptionAnalysisResponse | null>(null);
    const [fixesToApply, setFixesToApply] = useState<Set<string>>(new Set());
    const [error, setError] = useState<string | null>(null);
    const [isFolderSelectorOpen, setIsFolderSelectorOpen] = useState<boolean>(false);

    // --- Effects ---
    // Reset the modal to its initial state whenever it's opened.
    useEffect(() => {
        if (isOpen) {
            setStep('initial');
            setSelectedUiName('');
            setDisplayName(''); // --- NEW: Reset display name ---
            setSelectedPath('');
            setAnalysisResult(null);
            setFixesToApply(new Set());
            setError(null);
        }
    }, [isOpen]);

    // --- NEW: Effect to auto-populate display name when UI type is selected ---
    useEffect(() => {
        if (selectedUiName) {
            setDisplayName(selectedUiName);
        }
    }, [selectedUiName]);

    // --- Event Handlers ---
    const handleAnalyze = async () => {
        if (!selectedUiName || !selectedPath || !displayName.trim()) {
            setError('Please select a UI type, provide an instance name, and a directory path.');
            return;
        }
        setError(null);
        setStep('analyzing');
        try {
            const request: UiAdoptionAnalysisRequest = {
                ui_name: selectedUiName,
                path: selectedPath,
            };
            const result = await analyzeUiForAdoptionAPI(request);
            setAnalysisResult(result);

            const defaultFixes = new Set(
                result.issues
                    .filter((issue) => issue.is_fixable && issue.default_fix_enabled)
                    .map((issue) => issue.code),
            );
            setFixesToApply(defaultFixes);
            setStep('diagnosis');
        } catch (err: any) {
            setError(err.message || 'An unknown error occurred during analysis.');
            setStep('initial');
        }
    };

    const handleToggleFix = (issueCode: string) => {
        setFixesToApply((prev) => {
            const newSet = new Set(prev);
            if (newSet.has(issueCode)) {
                newSet.delete(issueCode);
            } else {
                newSet.add(issueCode);
            }
            return newSet;
        });
    };

    // --- REFACTOR: Handlers now pass the display name to the callback ---
    const handleRepair = () => {
        if (!selectedUiName || !selectedPath || !displayName.trim()) return;
        onConfirmRepair(selectedUiName, displayName.trim(), selectedPath, Array.from(fixesToApply));
        onClose();
    };

    const handleFinalize = () => {
        if (!selectedUiName || !selectedPath || !displayName.trim()) return;
        onConfirmFinalize(selectedUiName, displayName.trim(), selectedPath);
        onClose();
    };

    // --- Render Logic ---
    const renderInitialStep = () => (
        <>
            <div className="form-section">
                <label htmlFor="uiNameSelect" className="config-label">
                    Which UI are you adopting?
                </label>
                <select
                    id="uiNameSelect"
                    value={selectedUiName}
                    onChange={(e) => setSelectedUiName(e.target.value as UiNameType)}
                    className="config-select"
                >
                    <option value="" disabled>
                        Select a UI...
                    </option>
                    {availableUis.map((ui) => (
                        <option key={ui.ui_name} value={ui.ui_name}>
                            {ui.ui_name}
                        </option>
                    ))}
                </select>
            </div>
            {/* --- NEW: Display Name Input Field --- */}
            <div className="form-section">
                <label htmlFor="displayNameAdopt" className="config-label">
                    Instance Name
                </label>
                <div className="input-with-icon">
                    <CaseSensitive size={18} className="input-icon" />
                    <input
                        type="text"
                        id="displayNameAdopt"
                        value={displayName}
                        onChange={(e) => setDisplayName(e.target.value)}
                        placeholder="e.g., ComfyUI - Legacy"
                        className="config-input"
                    />
                </div>
                <p className="config-hint">
                    Give this existing installation a unique, memorable name.
                </p>
            </div>
            <div className="form-section">
                <label htmlFor="installPath" className="config-label">
                    Path to Existing Installation
                </label>
                <div className="base-path-selector">
                    <input
                        type="text"
                        id="installPath"
                        value={selectedPath}
                        onChange={(e) => setSelectedPath(e.target.value)}
                        placeholder="e.g., /path/to/my/ComfyUI"
                        className="config-input path-input"
                    />
                    <button onClick={() => setIsFolderSelectorOpen(true)} className="button">
                        <Folder size={16} /> Browse...
                    </button>
                </div>
            </div>
        </>
    );

    const renderDiagnosisStep = () => {
        if (!analysisResult) return null;

        if (!analysisResult.is_adoptable) {
            return (
                <div className="diagnosis-view error">
                    <ShieldAlert size={48} className="icon-error" />
                    <h3>Adoption Not Possible</h3>
                    <p>This installation has critical, unfixable issues.</p>
                    <ul className="issue-list">
                        {analysisResult.issues.map((issue) => (
                            <li key={issue.code}>- {issue.message}</li>
                        ))}
                    </ul>
                </div>
            );
        }

        if (analysisResult.is_healthy) {
            return (
                <div className="diagnosis-view success">
                    <CheckCircle size={48} className="icon-success" />
                    <h3>Installation Healthy</h3>
                    <p>
                        This installation appears to be in perfect condition and is ready for
                        adoption as '{displayName}'.
                    </p>
                </div>
            );
        }

        return (
            <div className="diagnosis-view issues">
                <HeartPulse size={48} className="icon-warning" />
                <h3>Diagnosis Report for '{displayName}'</h3>
                <p>
                    We found some issues with this installation. You can choose to repair them
                    automatically.
                </p>
                <ul className="issue-list">
                    {analysisResult.issues.map((issue) => (
                        <li
                            key={issue.code}
                            className={issue.is_fixable ? 'fixable' : 'not-fixable'}
                        >
                            {issue.is_fixable && (
                                <input
                                    type="checkbox"
                                    id={`fix-${issue.code}`}
                                    checked={fixesToApply.has(issue.code)}
                                    onChange={() => handleToggleFix(issue.code)}
                                />
                            )}
                            <label htmlFor={`fix-${issue.code}`}>
                                <div className="issue-text-content">
                                    <strong>{issue.message}</strong>
                                    {issue.is_fixable && <span>{issue.fix_description}</span>}
                                </div>
                            </label>
                        </li>
                    ))}
                </ul>
            </div>
        );
    };

    const renderModalBody = () => {
        switch (step) {
            case 'initial':
                return renderInitialStep();
            case 'analyzing':
                return (
                    <div className="loading-view">
                        <Loader2 size={32} className="animate-spin" />
                        <p>Analyzing directory...</p>
                    </div>
                );
            case 'diagnosis':
                return renderDiagnosisStep();
            default:
                return null;
        }
    };

    const renderModalActions = () => {
        const isAnalyzeDisabled =
            !selectedUiName || !selectedPath || !displayName.trim() || step === 'analyzing';

        if (step === 'initial' || step === 'analyzing') {
            return (
                <>
                    <button onClick={onClose} className="button" disabled={step === 'analyzing'}>
                        Cancel
                    </button>
                    <button
                        onClick={handleAnalyze}
                        className="button button-primary"
                        disabled={isAnalyzeDisabled}
                    >
                        {step === 'analyzing' ? (
                            <Loader2 size={18} className="animate-spin" />
                        ) : (
                            <HeartPulse size={18} />
                        )}
                        {step === 'analyzing' ? 'Analyzing...' : 'Analyze'}
                    </button>
                </>
            );
        }

        if (step === 'diagnosis' && analysisResult) {
            if (!analysisResult.is_adoptable) {
                return (
                    <button onClick={onClose} className="button">
                        Close
                    </button>
                );
            }
            if (analysisResult.is_healthy) {
                return (
                    <>
                        <button onClick={onClose} className="button">
                            Cancel
                        </button>
                        <button onClick={handleFinalize} className="button button-primary">
                            <ClipboardCheck size={18} /> Adopt
                        </button>
                    </>
                );
            }
            // Has fixable issues
            return (
                <>
                    <button onClick={handleFinalize} className="button">
                        Adopt Anyway
                    </button>
                    <button
                        onClick={handleRepair}
                        className="button button-primary"
                        disabled={fixesToApply.size === 0}
                    >
                        <CheckCircle size={18} /> Repair & Adopt ({fixesToApply.size})
                    </button>
                </>
            );
        }

        return (
            <button onClick={onClose} className="button">
                Close
            </button>
        );
    };

    if (!isOpen) return null;

    return (
        <>
            <div className="modal-overlay active">
                <div
                    className="modal-content adopt-modal-content"
                    onClick={(e) => e.stopPropagation()}
                >
                    <div className="modal-header">
                        <div className="modal-header-content">
                            <ClipboardCheck size={22} className="header-icon" />
                            <h3>Adopt Existing UI</h3>
                        </div>
                        <button
                            onClick={onClose}
                            className="button-icon close-button"
                            aria-label="Close"
                        >
                            <X size={20} />
                        </button>
                    </div>
                    <div className="modal-body adopt-modal-body">
                        {renderModalBody()}
                        {error && (
                            <div className="feedback-message error">
                                <AlertTriangle size={16} />
                                <span>{error}</span>
                            </div>
                        )}
                    </div>
                    <div className="modal-actions">{renderModalActions()}</div>
                </div>
            </div>
            <FolderSelector
                isOpen={isFolderSelectorOpen}
                onSelectFinalPath={(path) => {
                    setSelectedPath(path);
                    setIsFolderSelectorOpen(false);
                }}
                onCancel={() => setIsFolderSelectorOpen(false)}
            />
        </>
    );
};

export default AdoptUiModal;

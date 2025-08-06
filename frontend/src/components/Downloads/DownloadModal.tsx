// frontend/src/components/Downloads/DownloadModal.tsx
import React, { useState, useEffect } from 'react';
import { type ModelDetails, type ModelFile, type ModelType, downloadFileAPI } from '~/api';
import { X, Loader2, Download, AlertTriangle } from 'lucide-react';

interface DownloadModalProps {
    isOpen: boolean;
    onClose: () => void;
    modelDetails: ModelDetails | null;
    specificFileToDownload?: ModelFile | null;
    onDownloadsStarted: () => void;
}

/**
 * @fix {CRITICAL} Corrected the string literals to match the backend's ModelType.
 * The values are now capitalized (e.g., 'Checkpoint' instead of 'checkpoints')
 * to prevent API validation errors (HTTP 422) upon submitting a download request.
 */
const COMMON_MODEL_TYPES: ModelType[] = [
    'Checkpoint',
    'LoRA',
    'VAE',
    'TextualInversion', // Corrected from 'embeddings'
    'ControlNet',
    'Upscaler', // Added for completeness
    'Hypernetwork',
    'LyCORIS', // Added for completeness
    'MotionModule', // Added for completeness
    'Other', // Changed from 'custom' to 'Other' to match backend
];

const DownloadModal: React.FC<DownloadModalProps> = ({
    isOpen,
    onClose,
    modelDetails,
    specificFileToDownload,
    onDownloadsStarted,
}) => {
    const [selectedFiles, setSelectedFiles] = useState<
        Record<string, { file: ModelFile; modelType: ModelType; customPath?: string }>
    >({});

    const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    /**
     * @fix {CRITICAL} Updated the guessing logic to return the correct, capitalized ModelType values.
     * This ensures that the initial state of the dropdowns is valid according to the API.
     */
    const guessModelTypeFromFile = (filename: string): ModelType | null => {
        const fnLower = filename.toLowerCase();
        if (
            fnLower.includes('checkpoint') ||
            fnLower.endsWith('.ckpt') ||
            fnLower.endsWith('.safetensors')
        )
            return 'Checkpoint';
        if (fnLower.includes('lora')) return 'LoRA';
        if (fnLower.includes('lycoris')) return 'LyCORIS';
        if (fnLower.includes('vae')) return 'VAE';
        if (fnLower.includes('embedding')) return 'TextualInversion';
        if (fnLower.includes('controlnet')) return 'ControlNet';
        if (fnLower.includes('upscal')) return 'Upscaler';
        if (fnLower.includes('hypernetwork')) return 'Hypernetwork';
        if (fnLower.includes('motion')) return 'MotionModule';
        return null;
    };

    useEffect(() => {
        if (isOpen && modelDetails) {
            const initialSelected: typeof selectedFiles = {};
            const filesToConsider = specificFileToDownload
                ? [specificFileToDownload]
                : modelDetails.siblings || [];

            filesToConsider.forEach((file) => {
                const initialModelType = guessModelTypeFromFile(file.rfilename) || 'Other';
                initialSelected[file.rfilename] = {
                    file,
                    modelType: initialModelType,
                    customPath:
                        initialModelType === 'Other'
                            ? file.rfilename.substring(0, file.rfilename.lastIndexOf('/') + 1) ||
                              'other/'
                            : undefined,
                };
            });

            setSelectedFiles(initialSelected);
            setIsSubmitting(false);
            setError(null);
        }
    }, [isOpen, modelDetails, specificFileToDownload]);

    const handleFileSelectionChange = (file: ModelFile, isSelected: boolean) => {
        setSelectedFiles((prev) => {
            const newSelected = { ...prev };
            if (isSelected) {
                const initialModelType = guessModelTypeFromFile(file.rfilename) || 'Other';
                newSelected[file.rfilename] = { file, modelType: initialModelType };
            } else {
                delete newSelected[file.rfilename];
            }
            return newSelected;
        });
    };

    const handleModelTypeChange = (filename: string, modelType: ModelType) => {
        setSelectedFiles((prev) => ({ ...prev, [filename]: { ...prev[filename], modelType } }));
    };

    const handleCustomPathChange = (filename: string, path: string) => {
        setSelectedFiles((prev) => ({
            ...prev,
            [filename]: { ...prev[filename], customPath: path },
        }));
    };

    const handleSelectAllChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const isChecked = e.target.checked;
        if (isChecked) {
            const allSelected: typeof selectedFiles = {};
            modelDetails?.siblings?.forEach((file) => {
                const initialModelType = guessModelTypeFromFile(file.rfilename) || 'Other';
                allSelected[file.rfilename] = {
                    file,
                    modelType: initialModelType,
                    customPath:
                        initialModelType === 'Other'
                            ? file.rfilename.substring(0, file.rfilename.lastIndexOf('/') + 1) ||
                              'other/'
                            : undefined,
                };
            });
            setSelectedFiles(allSelected);
        } else {
            setSelectedFiles({});
        }
    };

    const handleStartDownloads = async () => {
        if (!modelDetails || Object.keys(selectedFiles).length === 0) return;

        setIsSubmitting(true);
        setError(null);

        const downloadPromises = Object.values(selectedFiles).map((selection) =>
            downloadFileAPI({
                source: modelDetails.source,
                repo_id: modelDetails.id,
                filename: selection.file.rfilename,
                model_type: selection.modelType,
                custom_sub_path: selection.modelType === 'Other' ? selection.customPath : undefined,
            }),
        );

        try {
            // We use Promise.allSettled to handle individual failures without stopping all downloads.
            const results = await Promise.allSettled(downloadPromises);

            // Check if at least one download was initiated successfully.
            const wasAnySuccess = results.some((res) => res.status === 'fulfilled');

            if (wasAnySuccess) {
                // Signal the App to take over, which will close this modal and open the sidebar.
                onDownloadsStarted();
            } else {
                // If all promises were rejected, show a generic error.
                const firstError = results.find((res) => res.status === 'rejected') as
                    | PromiseRejectedResult
                    | undefined;
                throw new Error(
                    firstError?.reason?.message || 'None of the downloads could be started.',
                );
            }
        } catch (err: any) {
            setError(err.message || 'An error occurred while starting downloads.');
        } finally {
            // We don't set isSubmitting to false if successful, as the modal will close.
            // If there's an error, we allow the user to try again.
            if (error) {
                setIsSubmitting(false);
            }
        }
    };

    if (!isOpen || !modelDetails) return null;

    const filesToList = modelDetails.siblings || [];
    const numSelected = Object.keys(selectedFiles).length;
    const isAllSelected = filesToList.length > 0 && numSelected === filesToList.length;

    return (
        <div className="modal-overlay download-modal-overlay active">
            <div
                className="modal-content download-modal-content"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="modal-header">
                    <div className="download-modal-header-text">
                        <h3>Download Files</h3>
                        <span>
                            For model: <strong>{modelDetails.model_name}</strong>
                        </span>
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

                <div className="modal-body download-modal-body">
                    <div className="download-modal-controls">
                        <div className="select-all-container">
                            <input
                                type="checkbox"
                                id="select-all-files"
                                checked={isAllSelected}
                                onChange={handleSelectAllChange}
                                disabled={isSubmitting || filesToList.length === 0}
                            />
                            <label htmlFor="select-all-files">Select All</label>
                        </div>
                        <span className="selection-count">
                            {numSelected} / {filesToList.length} files selected
                        </span>
                    </div>
                    <div className="download-modal-file-list">
                        {filesToList.length > 0 ? (
                            filesToList.map((file) => {
                                const isSelected = !!selectedFiles[file.rfilename];
                                return (
                                    <div
                                        key={file.rfilename}
                                        className={`download-file-item ${
                                            isSelected ? 'selected' : ''
                                        }`}
                                    >
                                        <div className="file-item-main-info">
                                            <input
                                                type="checkbox"
                                                id={`cb-${file.rfilename}`}
                                                checked={isSelected}
                                                onChange={(e) =>
                                                    handleFileSelectionChange(
                                                        file,
                                                        e.target.checked,
                                                    )
                                                }
                                                disabled={isSubmitting}
                                                aria-labelledby={`label-${file.rfilename}`}
                                            />
                                            <label
                                                htmlFor={`cb-${file.rfilename}`}
                                                id={`label-${file.rfilename}`}
                                                className="file-name-label"
                                            >
                                                {file.rfilename}
                                            </label>
                                        </div>
                                        {isSelected && (
                                            <div className="file-item-options">
                                                <select
                                                    value={selectedFiles[file.rfilename].modelType}
                                                    onChange={(e) =>
                                                        handleModelTypeChange(
                                                            file.rfilename,
                                                            e.target.value as ModelType,
                                                        )
                                                    }
                                                    disabled={isSubmitting}
                                                    className="config-select"
                                                >
                                                    {COMMON_MODEL_TYPES.map((type) => (
                                                        <option key={type} value={type}>
                                                            {type}
                                                        </option>
                                                    ))}
                                                </select>
                                                {selectedFiles[file.rfilename].modelType ===
                                                    'Other' && (
                                                    <input
                                                        type="text"
                                                        placeholder="Enter relative path..."
                                                        value={
                                                            selectedFiles[file.rfilename]
                                                                .customPath || ''
                                                        }
                                                        onChange={(e) =>
                                                            handleCustomPathChange(
                                                                file.rfilename,
                                                                e.target.value,
                                                            )
                                                        }
                                                        disabled={isSubmitting}
                                                        className="config-input"
                                                    />
                                                )}
                                            </div>
                                        )}
                                    </div>
                                );
                            })
                        ) : (
                            <p className="no-results-message">No files found for this model.</p>
                        )}
                    </div>
                    {error && (
                        <div className="feedback-message error">
                            <AlertTriangle size={16} />
                            <span>{error}</span>
                        </div>
                    )}
                </div>

                <div className="modal-actions">
                    <button onClick={onClose} className="button" disabled={isSubmitting}>
                        Cancel
                    </button>
                    <button
                        onClick={handleStartDownloads}
                        className="button button-primary"
                        disabled={isSubmitting || numSelected === 0}
                    >
                        {isSubmitting ? (
                            <Loader2 size={18} className="animate-spin" />
                        ) : (
                            <>
                                <Download size={18} />
                                {`Start Download (${numSelected})`}
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default DownloadModal;

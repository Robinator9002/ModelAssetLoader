// frontend/src/components/Files/DownloadModal.tsx
import React, { useState, useEffect, useCallback } from "react";
import {
	type ModelDetails,
	type ModelFile,
	type ModelType,
	downloadFileAPI,
} from "../../api/api";
import { X, Loader2 } from "lucide-react";

interface DownloadModalProps {
	isOpen: boolean;
	onClose: () => void;
	modelDetails: ModelDetails | null;
	specificFileToDownload?: ModelFile | null;
}

const COMMON_MODEL_TYPES: ModelType[] = [
	"checkpoints", "loras", "vae", "embeddings", "controlnet", 
    "diffusers", "clip", "unet", "hypernetworks", "custom"
];

const DownloadModal: React.FC<DownloadModalProps> = ({
	isOpen,
	onClose,
	modelDetails,
	specificFileToDownload,
}) => {
	// State for the selected files including their download configuration
	const [selectedFiles, setSelectedFiles] = useState<Record<string, { file: ModelFile; modelType: ModelType; customPath?: string }>>({});
	
    // REFACTOR: Removed local download status tracking.
    // The global DownloadManager is now responsible for showing progress.
	const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
	const [error, setError] = useState<string | null>(null);

	// Helper to guess the model type based on filename or path
	const guessModelTypeFromFile = (filename: string): ModelType | null => {
		const fnLower = filename.toLowerCase();
		if (fnLower.includes("checkpoint") || fnLower.endsWith(".ckpt") || fnLower.endsWith(".safetensors")) return "checkpoints";
		if (fnLower.includes("lora")) return "loras";
		if (fnLower.includes("vae")) return "vae";
		if (fnLower.includes("embedding")) return "embeddings";
		if (fnLower.includes("controlnet")) return "controlnet";
		// Add more rules as needed
		return null;
	};

	// Reset state when the modal is opened
	useEffect(() => {
		if (isOpen && modelDetails) {
			const initialSelected: typeof selectedFiles = {};
			const filesToConsider = specificFileToDownload ? [specificFileToDownload] : modelDetails.siblings || [];
			
			filesToConsider.forEach(file => {
				const initialModelType = guessModelTypeFromFile(file.rfilename) || "custom";
				initialSelected[file.rfilename] = {
					file,
					modelType: initialModelType,
					customPath: initialModelType === "custom" ? file.rfilename.substring(0, file.rfilename.lastIndexOf('/') + 1) || 'custom/' : undefined
				};
			});

			setSelectedFiles(initialSelected);
			setIsSubmitting(false);
			setError(null);
		}
	}, [isOpen, modelDetails, specificFileToDownload]);

	const handleFileSelectionChange = (file: ModelFile, isSelected: boolean) => {
		setSelectedFiles(prev => {
			const newSelected = { ...prev };
			if (isSelected) {
				const initialModelType = guessModelTypeFromFile(file.rfilename) || "custom";
				newSelected[file.rfilename] = { file, modelType: initialModelType };
			} else {
				delete newSelected[file.rfilename];
			}
			return newSelected;
		});
	};

	const handleModelTypeChange = (filename: string, modelType: ModelType) => {
		setSelectedFiles(prev => ({ ...prev, [filename]: { ...prev[filename], modelType } }));
	};
    
	const handleCustomPathChange = (filename: string, path: string) => {
		setSelectedFiles(prev => ({ ...prev, [filename]: { ...prev[filename], customPath: path } }));
	};

	const handleStartDownloads = async () => {
		if (!modelDetails || Object.keys(selectedFiles).length === 0) return;

		setIsSubmitting(true);
		setError(null);

		const downloadPromises = Object.values(selectedFiles).map(selection => 
			downloadFileAPI({
				source: modelDetails.source,
				repo_id: modelDetails.id,
				filename: selection.file.rfilename,
				model_type: selection.modelType,
				custom_sub_path: selection.modelType === "custom" ? selection.customPath : undefined,
			})
		);

		try {
			// Wait for all download *requests* to be acknowledged by the backend
			const results = await Promise.all(downloadPromises);
			
			// Check if any of the requests failed to be queued
			const firstError = results.find(res => !res.success);
			if (firstError) {
				throw new Error(firstError.error || "Ein Download konnte nicht gestartet werden.");
			}

			// If all requests were successfully queued, close the modal.
			// The global DownloadManager will now show the progress toasts.
			onClose();

		} catch (err: any) {
			setError(err.message || "Fehler beim Starten der Downloads.");
			setIsSubmitting(false); // Allow the user to try again
		}
	};

	if (!isOpen || !modelDetails) return null;

	const filesToList = modelDetails.siblings || [];

	return (
		<div className="modal-overlay download-modal-overlay active" onClick={isSubmitting ? undefined : onClose}>
			<div className="modal-content download-modal-content" onClick={(e) => e.stopPropagation()}>
				<div className="download-modal-header">
					<h3>Dateien für "{modelDetails.model_name}" auswählen</h3>
					<button onClick={onClose} className="close-button" disabled={isSubmitting}><X size={20} /></button>
				</div>

				<div className="download-modal-body">
					<div className="download-modal-file-list">
						{filesToList.length > 0 ? filesToList.map((file) => (
							<div key={file.rfilename} className={`download-file-item ${selectedFiles[file.rfilename] ? "selected" : ""}`}>
								<div className="file-item-main-info">
									<input
										type="checkbox"
										id={`cb-${file.rfilename}`}
										checked={!!selectedFiles[file.rfilename]}
										onChange={(e) => handleFileSelectionChange(file, e.target.checked)}
										disabled={isSubmitting}
									/>
									<label htmlFor={`cb-${file.rfilename}`} className="file-name-label">
										{file.rfilename}
									</label>
								</div>
								{selectedFiles[file.rfilename] && (
									<div className="file-item-options">
										<select
											value={selectedFiles[file.rfilename].modelType}
											onChange={(e) => handleModelTypeChange(file.rfilename, e.target.value as ModelType)}
											disabled={isSubmitting}
										>
											{COMMON_MODEL_TYPES.map(type => <option key={type} value={type}>{type}</option>)}
										</select>
										{selectedFiles[file.rfilename].modelType === 'custom' && (
											<input
												type="text"
												placeholder="Relativer Pfad..."
												value={selectedFiles[file.rfilename].customPath || ''}
												onChange={(e) => handleCustomPathChange(file.rfilename, e.target.value)}
												disabled={isSubmitting}
											/>
										)}
									</div>
								)}
							</div>
						)) : <p>Keine Dateien gefunden.</p>}
					</div>
					{error && <p className="error-message">{error}</p>}
				</div>

				<div className="download-modal-actions">
					<button onClick={onClose} className="button modal-button" disabled={isSubmitting}>Abbrechen</button>
					<button
						onClick={handleStartDownloads}
						className="button modal-button confirm-button button-primary"
						disabled={isSubmitting || Object.keys(selectedFiles).length === 0}
					>
						{isSubmitting ? (
							<Loader2 size={18} className="animate-spin" />
						) : (
							`Downloads starten (${Object.keys(selectedFiles).length})`
						)}
					</button>
				</div>
			</div>
		</div>
	);
};

export default DownloadModal;

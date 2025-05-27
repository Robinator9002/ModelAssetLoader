// frontend/src/components/Files/DownloadModal.tsx
import React, { useState, useEffect } from "react";
import {
	type HFModelDetails,
	type HFModelFile,
	type ModelType,
	downloadFileAPI,
} from "../../api/api";
import { X, Loader2 } from "lucide-react";

// CSS wird über die entsprechende CSS-Datei importiert (z.B. DownloadModal.css)
// Import './DownloadModal.css'; // Stellen Sie sicher, dass dieser Import vorhanden ist, wenn Sie CSS-Module oder direkten Import verwenden

interface DownloadModalProps {
	isOpen: boolean;
	onClose: () => void;
	modelDetails: HFModelDetails | null;
	specificFileToDownload?: HFModelFile | null; // Für den Fall, dass nur eine bestimmte Datei heruntergeladen werden soll
}

// Gängige Modelltypen, die im Dropdown zur Auswahl stehen
const COMMON_MODEL_TYPES: ModelType[] = [
	"checkpoints",
	"loras",
	"vae",
	"embeddings",
	"controlnet",
	"diffusers",
	"custom", // Für benutzerdefinierte Pfade
	"clip",
	"unet",
	"hypernetworks",
	// Weitere Typen können hier bei Bedarf ergänzt werden
];

// Interface für das Feedback-Objekt jeder herunterzuladenden Datei
interface DownloadFeedbackItem {
	id: string; // Eindeutige ID, meist der Dateiname
	fileName: string;
	status: "pending" | "downloading" | "success" | "error"; // Aktueller Status des Downloads
	message?: string; // Nachricht bei Erfolg oder Fehler
	progress?: number; // Fortschritt in Prozent (0-100)
}

const DownloadModal: React.FC<DownloadModalProps> = ({
	isOpen,
	onClose,
	modelDetails,
	specificFileToDownload,
}) => {
	// Zustand für die ausgewählten Dateien, inklusive Modelltyp und ggf. benutzerdefiniertem Pfad
	const [selectedFiles, setSelectedFiles] = useState<
		Record<
			string,
			{ file: HFModelFile; modelType: ModelType; customPath?: string }
		>
	>({});
	// Globaler Zustand, ob gerade ein Download-Prozess aktiv ist
	const [isDownloadingGlobal, setIsDownloadingGlobal] =
		useState<boolean>(false);
	// Zustand für das Feedback (Status, Nachrichten, Fortschritt) der einzelnen Downloads
	const [downloadFeedback, setDownloadFeedback] = useState<
		DownloadFeedbackItem[]
	>([]);

	// Effekt zum Zurücksetzen des Zustands, wenn das Modal geöffnet/geschlossen wird oder sich die Modelldetails ändern
	useEffect(() => {
		if (isOpen && modelDetails) {
			const initialSelected: Record<
				string,
				{ file: HFModelFile; modelType: ModelType; customPath?: string }
			> = {};
			// Wenn 'specificFileToDownload' übergeben wird, diese Datei vorauswählen
			if (specificFileToDownload) {
				const initialModelType =
					guessModelTypeFromFile(specificFileToDownload.rfilename) || "custom";
				initialSelected[specificFileToDownload.rfilename] = {
					file: specificFileToDownload,
					modelType: initialModelType,
					customPath:
						initialModelType === "custom"
							? extractDirectoryPath(specificFileToDownload.rfilename) ||
							  "downloads/" // Fallback-Pfad
							: undefined,
				};
			}
			setSelectedFiles(initialSelected);
			setDownloadFeedback([]); // Feedback-Array leeren
			setIsDownloadingGlobal(false); // Globalen Download-Status zurücksetzen
		} else if (!isOpen) {
			// Sicherstellen, dass beim Schließen alles zurückgesetzt wird
			setSelectedFiles({});
			setDownloadFeedback([]);
			setIsDownloadingGlobal(false);
		}
	}, [isOpen, modelDetails, specificFileToDownload]);

	// Hilfsfunktion, um den Verzeichnispfad aus einem vollständigen Dateipfad zu extrahieren
	const extractDirectoryPath = (filePath: string): string | undefined => {
		const lastSlash = filePath.lastIndexOf("/");
		if (lastSlash === -1) return undefined; // Kein Pfad gefunden
		return filePath.substring(0, lastSlash + 1); // Inklusive des letzten Slashs
	};

	// Hilfsfunktion, um den Modelltyp basierend auf dem Dateinamen zu erraten
	const guessModelTypeFromFile = (filename: string): ModelType | null => {
		const fnLower = filename.toLowerCase();
		if (
			fnLower.includes("checkpoint") ||
			fnLower.endsWith(".ckpt") ||
			fnLower.endsWith(".safetensors") ||
			fnLower.endsWith(".pth")
		)
			return "checkpoints";
		if (fnLower.includes("lora")) return "loras";
		if (fnLower.includes("vae")) return "vae";
		if (
			fnLower.includes("embedding") ||
			fnLower.includes("embed") ||
			fnLower.endsWith(".pt")
		)
			return "embeddings";
		if (fnLower.includes("controlnet") || fnLower.includes("control_net"))
			return "controlnet";
		if (fnLower.includes("hypernetwork")) return "hypernetworks";
		if (fnLower.includes("unet")) return "unet";
		if (fnLower.includes("clip")) return "clip";
		return null; // Kein passender Typ gefunden
	};

	// Handler für die Auswahl/Abwahl einer einzelnen Datei
	const handleFileSelectionChange = (
		file: HFModelFile,
		isSelected: boolean
	) => {
		setSelectedFiles((prev) => {
			const newSelected = { ...prev };
			if (isSelected) {
				const initialModelType =
					guessModelTypeFromFile(file.rfilename) || "custom";
				newSelected[file.rfilename] = {
					file,
					modelType: initialModelType,
					customPath:
						initialModelType === "custom"
							? extractDirectoryPath(file.rfilename) || "downloads/"
							: undefined,
				};
			} else {
				delete newSelected[file.rfilename]; // Datei aus Auswahl entfernen
			}
			return newSelected;
		});
	};

	// Handler für die Änderung des Modelltyps einer ausgewählten Datei
	const handleModelTypeChange = (filename: string, modelType: ModelType) => {
		setSelectedFiles((prev) => ({
			...prev,
			[filename]: {
				...prev[filename],
				modelType,
				// Benutzerdefinierten Pfad nur setzen/beibehalten, wenn Typ "custom" ist
				customPath:
					modelType === "custom"
						? prev[filename]?.customPath || // Bestehenden Pfad nehmen oder...
						  extractDirectoryPath(filename) || // Pfad aus Dateinamen extrahieren oder...
						  "downloads/" // Fallback
						: undefined, // Sonst Pfad entfernen
			},
		}));
	};

	// Handler für die Änderung des benutzerdefinierten Pfads
	const handleCustomPathChange = (filename: string, path: string) => {
		setSelectedFiles((prev) => ({
			...prev,
			[filename]: { ...prev[filename], customPath: path.trim() }, // Leerzeichen am Anfang/Ende entfernen
		}));
	};

	// Handler zum Starten des Downloads der ausgewählten Dateien
	const handleDownloadSelected = async () => {
		if (!modelDetails || Object.keys(selectedFiles).length === 0) return;

		setIsDownloadingGlobal(true); // Globalen Download-Status setzen
		// Initiales Feedback für alle ausgewählten Dateien erstellen
		const initialFeedback: DownloadFeedbackItem[] = Object.values(
			selectedFiles
		).map(({ file }) => ({
			id: file.rfilename,
			fileName: file.rfilename,
			status: "pending",
			progress: 0, // Fortschritt initial auf 0 setzen
		}));
		setDownloadFeedback(initialFeedback);

		// Dateien sequenziell herunterladen, um das Feedback-Management zu vereinfachen
		for (const selectionKey in selectedFiles) {
			const selection = selectedFiles[selectionKey];
			if (!selection) continue; // Sollte nicht passieren, aber sicher ist sicher
			const { file, modelType, customPath } = selection;

			// Feedback für die aktuelle Datei auf "downloading" setzen und Fortschritt simulieren (Start)
			setDownloadFeedback((prev) =>
				prev.map((fb) =>
					fb.id === file.rfilename
						? { ...fb, status: "downloading", progress: 5 } // Simulierter Start bei 5%
						: fb
				)
			);

			try {
				// API-Aufruf zum Herunterladen der Datei
				const response = await downloadFileAPI({
					repo_id: modelDetails.id,
					filename: file.rfilename, // Der vollständige Pfad/Name von Hugging Face
					model_type: modelType,
					custom_sub_path: modelType === "custom" ? customPath : undefined,
					// revision: undefined, // Optional: hier könnte eine spezifische Revision übergeben werden
				});

				// Feedback nach dem Download aktualisieren
				setDownloadFeedback((prev) =>
					prev.map((fb) =>
						fb.id === file.rfilename
							? {
									...fb,
									status: response.success ? "success" : "error",
									message: response.success
										? response.message || "Erfolgreich heruntergeladen."
										: response.error || "Fehlgeschlagen.",
									progress: response.success ? 100 : undefined, // Bei Erfolg auf 100%, sonst Fortschritt entfernen
							  }
							: fb
					)
				);
			} catch (err: any) {
				console.error("Download error for file:", file.rfilename, err);
				// Feedback bei einem Fehler aktualisieren
				setDownloadFeedback((prev) =>
					prev.map((fb) =>
						fb.id === file.rfilename
							? {
									...fb,
									status: "error",
									message: err.message || "Unbekannter Fehler beim Download.",
									progress: undefined, // Fortschritt bei Fehler entfernen
							  }
							: fb
					)
				);
			}
		}
		setIsDownloadingGlobal(false); // Globalen Download-Status zurücksetzen, wenn alle Downloads abgeschlossen sind
	};

	// Wenn das Modal nicht offen ist, nichts rendern
	if (!isOpen) {
		return null;
	}

	// Fallback-Anzeige, wenn Modelldetails noch geladen werden
	if (!modelDetails) {
		return (
			<div
				className={`modal-overlay download-modal-overlay ${
					isOpen ? "active" : ""
				}`}
			>
				<div className="modal-content download-modal-content">
					<div className="download-modal-header">
						<h3>Lade Modelldetails...</h3>
						<button
							onClick={onClose}
							className="close-button"
							title="Schließen"
							disabled={isDownloadingGlobal} // Schließen-Button während des Downloads deaktivieren
						>
							<X size={20} />
						</button>
					</div>
					<div className="loading-indicator-modal-body">
						<Loader2 size={32} className="animate-spin" />
						<p>Modelldaten werden geladen. Bitte warten...</p>
					</div>
				</div>
			</div>
		);
	}

	// Liste der anzuzeigenden Dateien (entweder eine spezifische oder alle "siblings")
	const filesToList = specificFileToDownload
		? [specificFileToDownload]
		: modelDetails.siblings || [];

	// Prüfen, ob alle angezeigten Dateien ausgewählt sind (für "Alle auswählen"-Checkbox)
	const allFilesSelected =
		filesToList.length > 0 &&
		filesToList.every((file) => !!selectedFiles[file.rfilename]);

	// Handler für die "Alle auswählen/abwählen"-Checkbox
	const handleSelectAllFiles = (selectAll: boolean) => {
		if (selectAll) {
			const newSelectedFiles: typeof selectedFiles = {};
			filesToList.forEach((file) => {
				const initialModelType =
					guessModelTypeFromFile(file.rfilename) || "custom";
				newSelectedFiles[file.rfilename] = {
					file,
					modelType: initialModelType,
					customPath:
						initialModelType === "custom"
							? extractDirectoryPath(file.rfilename) || "downloads/"
							: undefined,
				};
			});
			setSelectedFiles(newSelectedFiles);
		} else {
			setSelectedFiles({}); // Alle abwählen
		}
	};

	return (
		<div
			className={`modal-overlay download-modal-overlay ${
				isOpen ? "active" : ""
			}`}
			onClick={isDownloadingGlobal ? undefined : onClose} // Schließen bei Klick auf Overlay, außer wenn Download läuft
		>
			<div
				className="modal-content download-modal-content"
				onClick={(e) => e.stopPropagation()} // Verhindert, dass Klick im Modal das Modal schließt
			>
				<div className="download-modal-header">
					<h3>Dateien für "{modelDetails.model_name || modelDetails.id}"</h3>
					<button
						onClick={onClose}
						className="close-button"
						title="Schließen"
						disabled={isDownloadingGlobal}
					>
						<X size={20} />
					</button>
				</div>
				<div className="download-modal-body">
					{/* "Alle auswählen" nur anzeigen, wenn mehrere Dateien zur Auswahl stehen */}
					{filesToList.length > 1 && !specificFileToDownload && (
						<div className="select-all-container">
							<input
								type="checkbox"
								id="select-all-files"
								checked={allFilesSelected}
								onChange={(e) => handleSelectAllFiles(e.target.checked)}
								disabled={isDownloadingGlobal}
							/>
							<label htmlFor="select-all-files">
								Alle Dateien auswählen/abwählen
							</label>
						</div>
					)}
					<div className="download-modal-file-list">
						{filesToList.length > 0 ? (
							filesToList.map((file) => (
								<div
									key={file.rfilename}
									className={`download-file-item ${
										selectedFiles[file.rfilename] ? "selected" : ""
									}`}
								>
									<div className="file-item-main-info">
										<input
											type="checkbox"
											// Eindeutige ID für die Checkbox generieren
											id={`cb-${file.rfilename.replace(/[^a-zA-Z0-9]/g, "-")}`}
											checked={!!selectedFiles[file.rfilename]}
											onChange={(e) =>
												handleFileSelectionChange(file, e.target.checked)
											}
											disabled={isDownloadingGlobal}
										/>
										<label
											htmlFor={`cb-${file.rfilename.replace(
												/[^a-zA-Z0-9]/g,
												"-"
											)}`}
											className="file-name-label"
										>
											<span className="file-name" title={file.rfilename}>
												{file.rfilename}
											</span>
											<span className="file-size">
												(
												{file.size && file.size > 0
													? (file.size / (1024 * 1024)).toFixed(2) + " MB"
													: "Größe unbekannt"}
												)
											</span>
										</label>
									</div>
									{/* Optionen (Modelltyp, Pfad) nur anzeigen, wenn Datei ausgewählt ist */}
									{selectedFiles[file.rfilename] && (
										<div className="file-item-options">
											<select
												value={selectedFiles[file.rfilename].modelType}
												onChange={(e) =>
													handleModelTypeChange(
														file.rfilename,
														e.target.value as ModelType
													)
												}
												className="config-select model-type-select"
												disabled={isDownloadingGlobal}
											>
												{COMMON_MODEL_TYPES.map((type) => (
													<option key={type} value={type}>
														{type.charAt(0).toUpperCase() + type.slice(1)}
													</option>
												))}
											</select>
											{selectedFiles[file.rfilename].modelType === "custom" && (
												<input
													type="text"
													placeholder="Rel. Pfad (z.B. custom/loras)"
													value={selectedFiles[file.rfilename].customPath || ""}
													onChange={(e) =>
														handleCustomPathChange(
															file.rfilename,
															e.target.value
														)
													}
													className="config-input custom-path-input"
													disabled={isDownloadingGlobal}
												/>
											)}
										</div>
									)}
								</div>
							))
						) : (
							<p className="no-files-message">
								Keine herunterladbaren Dateien in diesem Modell gefunden.
							</p>
						)}
					</div>
					{/* Bereich für Download-Feedback und Ladebalken */}
					{downloadFeedback.length > 0 && (
						<div className="download-feedback-container">
							<h4>Download-Status:</h4>
							{downloadFeedback.map((fb) => (
								<div
									key={fb.id}
									className={`feedback-item-wrapper ${fb.status}`}
								>
									<div className="feedback-item-info">
										<strong>{fb.fileName}:</strong>{" "}
										{fb.status === "pending" && "Wartet..."}
										{fb.status === "downloading" && (
											<>
												<Loader2
													size={14}
													className="animate-spin inline-icon"
												/>{" "}
												Wird heruntergeladen...
											</>
										)}
										{fb.status !== "pending" &&
											fb.status !== "downloading" &&
											(fb.message || fb.status)}
									</div>
									{/* Ladebalken anzeigen, wenn Status "downloading" oder "success" */}
									{(fb.status === "downloading" || fb.status === "success") &&
										fb.progress !== undefined && (
											<div className="progress-bar-container">
												<div
													className={`progress-bar ${
														fb.status === "success" ? "success" : ""
													}`}
													style={{ width: `${fb.progress}%` }}
													role="progressbar"
													aria-valuenow={fb.progress}
													aria-valuemin={0}
													aria-valuemax={100}
													title={`${fb.progress}%`}
												>
													<span className="progress-bar-text">
														{fb.progress}%
													</span>
												</div>
											</div>
										)}
								</div>
							))}
						</div>
					)}
				</div>
				<div className="download-modal-actions">
					<button
						className="button modal-button cancel-button"
						onClick={onClose}
						disabled={isDownloadingGlobal}
					>
						Abbrechen
					</button>
					<button
						className="button modal-button confirm-button button-primary"
						onClick={handleDownloadSelected}
						disabled={
							isDownloadingGlobal || Object.keys(selectedFiles).length === 0
						}
					>
						{isDownloadingGlobal ? (
							<>
								<Loader2 size={18} className="animate-spin inline-icon" /> Lädt
								herunter...
							</>
						) : (
							`Ausgewählte (${Object.keys(selectedFiles).length}) herunterladen`
						)}
					</button>
				</div>
			</div>
		</div>
	);
};

export default DownloadModal;

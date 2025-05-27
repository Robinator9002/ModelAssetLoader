// frontend/src/components/ModelLoader/ModelDetailsPage.tsx
import React, { useState, useEffect } from "react";
import {
	getModelDetails,
	type HFModelDetails,
	type HFModelFile,
} from "../../api/api";
import ReactMarkdown from "react-markdown";
import { Download, ArrowLeft } from "lucide-react"; // Beispiel Icons

// Für Syntax Highlighting (optional, aber empfohlen für READMEs)
// import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
// import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'; // Wähle ein passendes Theme

interface ModelDetailsPageProps {
	modelId: string;
	onBack: () => void;
	openDownloadModal: (
		modelDetails: HFModelDetails,
		specificFile?: HFModelFile
	) => void;
	// isConfigurationDone: boolean; // Wird hier nicht direkt benötigt, da DownloadModal die Prüfung macht
}

const ModelDetailsPage: React.FC<ModelDetailsPageProps> = ({
	modelId,
	onBack,
	openDownloadModal,
}) => {
	const [details, setDetails] = useState<HFModelDetails | null>(null);
	const [isLoading, setIsLoading] = useState<boolean>(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		const fetchDetails = async () => {
			setIsLoading(true);
			setError(null);
			setDetails(null); // Wichtig, um alte Details zu entfernen
			try {
				const parts = modelId.split("/");
				if (parts.length < 2) throw new Error("Ungültige Modell-ID.");
				const author = parts[0];
				const modelName = parts.slice(1).join("/");
				const data = await getModelDetails(author, modelName);
				if (data) setDetails(data);
				else setError("Keine Modelldetails vom Server erhalten.");
			} catch (err: any) {
				setError(err.message || "Fehler beim Laden der Modelldetails.");
				console.error(err);
			} finally {
				setIsLoading(false);
			}
		};
		if (modelId) fetchDetails();
		else setIsLoading(false); // Sollte nicht passieren, wenn modelId immer gesetzt ist
	}, [modelId]);

	const formatFileSize = (bytes?: number | null): string => {
		if (bytes == null || bytes <= 0) return "0 Bytes"; // Geändert zu <= 0
		const k = 1024;
		const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
		const i = Math.floor(Math.log(bytes) / Math.log(k));
		return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
	};

	const handleDownloadFile = (file: HFModelFile) => {
		if (details) {
			openDownloadModal(details, file);
		}
	};

	if (isLoading)
		return (
			<p className="loading-message details-loading">Lade Modelldetails...</p>
		);
	if (error)
		return (
			<div className="model-details-page">
				<div className="details-page-header">
					<button
						onClick={onBack}
						className="back-button error-page-back-button"
					>
						<ArrowLeft size={18} style={{ marginRight: "0.25rem" }} />
						Zurück
					</button>
				</div>
				<div className="details-content-wrapper">
					<p className="error-message">{error}</p>
				</div>
			</div>
		);
	if (!details)
		return (
			<div className="model-details-page">
				<div className="details-page-header">
					<button onClick={onBack} className="back-button">
						<ArrowLeft size={18} style={{ marginRight: "0.25rem" }} />
						Zurück
					</button>
				</div>
				<div className="details-content-wrapper">
					<p className="no-results-message">Modelldetails nicht gefunden.</p>
				</div>
			</div>
		);

	return (
		<div className="model-details-page">
			<div className="details-page-header">
				<button onClick={onBack} className="back-button">
					<ArrowLeft size={18} style={{ marginRight: "0.25rem" }} />
					Zurück
				</button>
				<header className="details-header">
					<h1>{details.model_name}</h1>
					<p className="details-author">von: {details.author || "Unbekannt"}</p>
					<div className="details-meta">
						<span>
							Downloads:{" "}
							{details.downloads != null
								? details.downloads.toLocaleString()
								: "N/A"}
						</span>
						<span>
							Likes:{" "}
							{details.likes != null ? details.likes.toLocaleString() : "N/A"}
						</span>
						<span>
							Zuletzt geändert:{" "}
							{details.lastModified
								? new Date(details.lastModified).toLocaleDateString()
								: "N/A"}
						</span>
						{details.pipeline_tag && (
							<span className="pipeline-tag details-pipeline-tag">
								{details.pipeline_tag}
							</span>
						)}
						{details.library_name && (
							<span className="library-tag">Lib: {details.library_name}</span>
						)}
					</div>
				</header>
			</div>

			<div className="details-content-wrapper">
				{details.tags && details.tags.length > 0 && (
					<section className="details-section tags-section">
						<h2>Tags</h2>
						<div className="tags-list">
							{details.tags.map((tag) => (
								<span key={tag} className="tag-item">
									{tag}
								</span>
							))}
						</div>
					</section>
				)}

				<section className="details-section files-section">
					<h2>Dateien ({details.siblings ? details.siblings.length : 0})</h2>
					{details.siblings && details.siblings.length > 0 ? (
						<div className="files-list-container">
							<ul className="files-list">
								{details.siblings.map((file: HFModelFile) => (
									<li key={file.rfilename} className="file-item">
										<span className="file-name">{file.rfilename}</span>
										<span className="file-size">
											{formatFileSize(file.size)}
										</span>
										<button
											className="button-icon download-file-button"
											onClick={() => handleDownloadFile(file)}
											title={`Datei ${file.rfilename} herunterladen`}
										>
											<Download size={18} />
										</button>
									</li>
								))}
							</ul>
						</div>
					) : (
						<p>Keine Dateien für dieses Modell verfügbar.</p>
					)}
				</section>

				{details.readme_content ? (
					<section className="details-section readme-section">
						<h2>README.md</h2>
						<div className="readme-content">
							<ReactMarkdown
							// Optional: Komponenten für Syntax Highlighting
							// components={{
							//   code({node, inline, className, children, ...props}) {
							//     const match = /language-(\w+)/.exec(className || '')
							//     return !inline && match ? (
							//       <SyntaxHighlighter style={oneDark} language={match[1]} PreTag="div" {...props}>
							//         {String(children).replace(/\n$/, '')}
							//       </SyntaxHighlighter>
							//     ) : (
							//       <code className={className} {...props}>
							//         {children}
							//       </code>
							//     )
							//   }
							// }}
							>
								{details.readme_content}
							</ReactMarkdown>
						</div>
					</section>
				) : (
					<section className="details-section readme-section">
						<h2>README.md</h2>
						<p>Kein README für dieses Modell verfügbar.</p>
					</section>
				)}
			</div>
		</div>
	);
};

export default ModelDetailsPage;

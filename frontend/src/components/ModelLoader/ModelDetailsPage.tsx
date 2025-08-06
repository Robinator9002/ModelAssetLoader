// frontend/src/components/ModelLoader/ModelDetailsPage.tsx
import React, { useState, useEffect } from 'react';
import {
    getModelDetails,
    type ModelDetails,
    type ModelListItem,
} from '../../api/api';
// --- REFACTOR: Import the new modal store ---
import { useModalStore } from '../../state/modalStore';
import ReactMarkdown from 'react-markdown';
import { Download, ArrowLeft, Loader2, AlertTriangle, FileText, Files } from 'lucide-react';

interface ModelDetailsPageProps {
    selectedModel: ModelListItem;
    onBack: () => void;
    // --- REFACTOR: The openDownloadModal prop is no longer needed ---
    // openDownloadModal: (modelDetails: ModelDetails, specificFile?: ModelFile) => void;
}

/**
 * @refactor This component is now decoupled from App.tsx for modal control.
 * It uses the `useModalStore` to open the download modal directly, removing
 * the need for the `openDownloadModal` prop.
 */
const ModelDetailsPage: React.FC<ModelDetailsPageProps> = ({ selectedModel, onBack }) => {
    // --- State from Zustand Store ---
    const { openDownloadModal } = useModalStore();

    // --- Local Component State ---
    const [details, setDetails] = useState<ModelDetails | null>(null);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    // --- Data Fetching ---
    useEffect(() => {
        const fetchDetails = async () => {
            setIsLoading(true);
            setError(null);
            try {
                const data = await getModelDetails(selectedModel.source, selectedModel.id);
                setDetails(data);
            } catch (err: any) {
                setError(err.message || 'Failed to load model details.');
            } finally {
                setIsLoading(false);
            }
        };
        fetchDetails();
    }, [selectedModel]);

    // --- Helper Functions ---
    const formatFileSize = (bytes?: number | null): string => {
        if (bytes === null || typeof bytes === 'undefined' || bytes === 0) return 'N/A';
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        return `${parseFloat((bytes / Math.pow(1024, i)).toFixed(2))} ${sizes[i]}`;
    };

    // --- Render Logic ---

    if (isLoading) {
        return (
            <div className="page-state-container">
                <Loader2 size={32} className="animate-spin" />
                <p>Loading model details...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="page-state-container">
                <AlertTriangle size={32} className="icon-error" />
                <p>{error}</p>
            </div>
        );
    }

    if (!details) {
        return (
            <div className="page-state-container">
                <p>Model details not found.</p>
            </div>
        );
    }

    return (
        <div className="model-details-page">
            <div className="details-page-header">
                <button onClick={onBack} className="button">
                    <ArrowLeft size={18} /> Back to Search
                </button>
                <header className="details-main-header">
                    <h1>{details.model_name}</h1>
                    <p>by: {details.author || 'Unknown'}</p>
                </header>
            </div>

            <div className="details-content-wrapper">
                <section className="details-section files-section">
                    <header className="section-header">
                        <h2>
                            <Files size={20} /> Files ({details.siblings?.length || 0})
                        </h2>
                        {/* --- REFACTOR: Call the store action directly --- */}
                        <button className="button" onClick={() => openDownloadModal(details)}>
                            <Download size={16} />
                            <span>Download All</span>
                        </button>
                    </header>
                    <ul className="files-list">
                        {details.siblings?.map((file) => (
                            <li key={file.rfilename} className="file-item">
                                <div className="file-item-info">
                                    <span className="file-item-name">{file.rfilename}</span>
                                    <span className="file-item-size">
                                        {formatFileSize(file.size)}
                                    </span>
                                </div>
                                {/* --- REFACTOR: Call the store action directly --- */}
                                <button
                                    onClick={() => openDownloadModal(details, file)}
                                    className="button-icon"
                                    title={`Download ${file.rfilename}`}
                                >
                                    <Download size={18} />
                                </button>
                            </li>
                        ))}
                    </ul>
                </section>

                <section className="details-section readme-section">
                    <header className="section-header">
                        <h2>
                            <FileText size={20} /> README.md
                        </h2>
                    </header>
                    <div className="readme-content">
                        <ReactMarkdown>
                            {details.readme_content || 'No README available.'}
                        </ReactMarkdown>
                    </div>
                </section>
            </div>
        </div>
    );
};

export default ModelDetailsPage;

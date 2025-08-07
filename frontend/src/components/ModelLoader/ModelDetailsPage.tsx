// frontend/src/components/ModelLoader/ModelDetailsPage.tsx
import React, { useState, useEffect } from 'react';
// --- FIX: Import useParams to read the model ID from the URL ---
import { useParams, useNavigate } from 'react-router-dom';
import {
    getModelDetails,
    type ModelDetails,
    type ModelFile, // --- FIX: Explicitly import ModelFile for clarity ---
} from '~/api';
import { useModalStore } from '../../state/modalStore';
import ReactMarkdown from 'react-markdown';
import { Download, ArrowLeft, Loader2, AlertTriangle, FileText, Files } from 'lucide-react';

// --- FIX: The component no longer needs to receive the selected model as a prop ---
interface ModelDetailsPageProps {
    onBack: () => void;
}

/**
 * @refactor This component is now self-sufficient. It uses `useParams`
 * from react-router-dom to get the model's source and ID directly from the URL.
 * This makes it independent of the parent component's state, solving the
 * redirect loop and allowing for direct navigation and page refreshes.
 */
const ModelDetailsPage: React.FC<ModelDetailsPageProps> = ({ onBack }) => {
    // --- Hooks ---
    // --- FIX: Get routing parameters and navigation function from the router ---
    const { source, modelId } = useParams<{ source: string; modelId: string }>();
    const navigate = useNavigate();

    // --- State from Zustand Store ---
    const { openDownloadModal } = useModalStore();

    // --- Local Component State ---
    const [details, setDetails] = useState<ModelDetails | null>(null);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    // --- Data Fetching ---
    useEffect(() => {
        // --- FIX: Fetch details using parameters from the URL. ---
        // If source or modelId are missing, we can't fetch data, so redirect.
        if (!source || !modelId) {
            console.error('Missing source or modelId in URL, redirecting.');
            navigate('/search');
            return;
        }

        const fetchDetails = async () => {
            setIsLoading(true);
            setError(null);
            try {
                // --- FIX: Use the URL params for the API call ---
                const data = await getModelDetails(source, modelId);
                setDetails(data);
            } catch (err: any) {
                setError(err.message || 'Failed to load model details.');
                console.error(err);
            } finally {
                setIsLoading(false);
            }
        };
        fetchDetails();
    }, [source, modelId, navigate]); // --- FIX: Dependency array now relies on URL params ---

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
                <button onClick={onBack} className="button mt-4">
                    Back to Search
                </button>
            </div>
        );
    }

    if (!details) {
        return (
            <div className="page-state-container">
                <p>Model details not found.</p>
                <button onClick={onBack} className="button mt-4">
                    Back to Search
                </button>
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
                        <button className="button" onClick={() => openDownloadModal(details)}>
                            <Download size={16} />
                            <span>Download All</span>
                        </button>
                    </header>
                    <ul className="files-list">
                        {details.siblings?.map((file: ModelFile) => (
                            <li key={file.rfilename} className="file-item">
                                <div className="file-item-info">
                                    <span className="file-item-name">{file.rfilename}</span>
                                    <span className="file-item-size">
                                        {formatFileSize(file.size)}
                                    </span>
                                </div>
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

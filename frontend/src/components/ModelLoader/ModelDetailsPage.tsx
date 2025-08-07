// frontend/src/components/ModelLoader/ModelDetailsPage.tsx
import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { getModelDetails, type ModelDetails, type ModelFile } from '~/api';
import { useModalStore } from '../../state/modalStore';
import ReactMarkdown from 'react-markdown';
import { Download, ArrowLeft, Loader2, AlertTriangle, FileText, Files } from 'lucide-react';

interface ModelDetailsPageProps {
    onBack: () => void;
}

/**
 * @refactor This component is now self-sufficient and more robust. It patiently
 * waits for the router to provide the URL parameters before fetching data,
 * which solves the redirect loop.
 */
const ModelDetailsPage: React.FC<ModelDetailsPageProps> = ({ onBack }) => {
    // --- Hooks ---
    const { source, '*': modelId } = useParams<{ source: string; '*': string }>();

    // --- State from Zustand Store ---
    const { openDownloadModal } = useModalStore();

    // --- Local Component State ---
    const [details, setDetails] = useState<ModelDetails | null>(null);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    // --- Data Fetching ---
    useEffect(() => {
        // --- FIX: The main logic change is here. ---
        // We now only proceed to fetch data if `source` and `modelId` are actually
        // present. If they are `undefined` on the initial render, this `if` block
        // is skipped. The component will re-render when the router provides the
        // params, and on that second render, this block will execute.
        if (source && modelId) {
            const fetchDetails = async () => {
                setIsLoading(true);
                setError(null);
                try {
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
        }
        // --- FIX: By removing the `else` block that was causing the redirect, ---
        // we break the loop. The component now correctly waits for its data.
    }, [source, modelId]); // --- FIX: `navigate` is no longer needed as a dependency.

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

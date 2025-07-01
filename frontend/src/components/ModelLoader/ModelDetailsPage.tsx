// frontend/src/components/ModelLoader/ModelDetailsPage.tsx
import React, { useState, useEffect } from "react";
import {
  getModelDetails,
  type ModelDetails,
  type ModelFile,
  type ModelListItem,
} from "../../api/api";
import ReactMarkdown from "react-markdown";
import { Download, ArrowLeft, Loader2, AlertTriangle, FileText, Files } from "lucide-react";

interface ModelDetailsPageProps {
  selectedModel: ModelListItem;
  onBack: () => void;
  openDownloadModal: (
    modelDetails: ModelDetails,
    specificFile?: ModelFile
  ) => void;
}

const ModelDetailsPage: React.FC<ModelDetailsPageProps> = ({
  selectedModel,
  onBack,
  openDownloadModal,
}) => {
  const [details, setDetails] = useState<ModelDetails | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchDetails = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const data = await getModelDetails(
          selectedModel.source,
          selectedModel.id
        );
        setDetails(data);
      } catch (err: any) {
        setError(err.message || "Failed to load model details.");
      } finally {
        setIsLoading(false);
      }
    };
    fetchDetails();
  }, [selectedModel]);

  const formatFileSize = (bytes?: number | null): string => {
    if (bytes === null || typeof bytes === 'undefined' || bytes === 0) return "N/A";
    const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${parseFloat((bytes / Math.pow(1024, i)).toFixed(2))} ${sizes[i]}`;
  };

  if (isLoading)
    return (
        <div className="feedback-placeholder">
            <Loader2 size={32} className="animate-spin" />
            <p>Loading model details...</p>
        </div>
    );

  if (error) 
    return (
        <div className="feedback-placeholder error-text">
            <AlertTriangle size={32} />
            <p>{error}</p>
        </div>
    );

  if (!details)
    return (
        <div className="feedback-placeholder">
            <p>Model details not found.</p>
        </div>
    );

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
            <h2><Files size={20}/> Files ({details.siblings?.length || 0})</h2>
            <button className="button" onClick={() => openDownloadModal(details)}>
                <Download size={16}/>
                <span>Download All</span>
            </button>
          </header>
          <ul className="files-list">
            {details.siblings?.map((file) => (
              <li key={file.rfilename} className="file-item">
                <div className="file-item-info">
                    <span className="file-item-name">{file.rfilename}</span>
                    <span className="file-item-size">{formatFileSize(file.size)}</span>
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
                <h2><FileText size={20}/> README.md</h2>
           </header>
          <div className="readme-content">
            <ReactMarkdown>
              {details.readme_content || "No README available."}
            </ReactMarkdown>
          </div>
        </section>
      </div>
    </div>
  );
};

export default ModelDetailsPage;

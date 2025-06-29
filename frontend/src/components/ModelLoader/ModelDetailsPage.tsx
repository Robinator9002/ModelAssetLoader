// frontend/src/components/ModelLoader/ModelDetailsPage.tsx
import React, { useState, useEffect } from "react";
import {
  getModelDetails,
  type ModelDetails, // REFACTOR: Generic type
  type ModelFile, // REFACTOR: Generic type
  type ModelListItem,
} from "../../api/api";
import ReactMarkdown from "react-markdown";
import { Download, ArrowLeft } from "lucide-react";

interface ModelDetailsPageProps {
  selectedModel: ModelListItem; // REFACTOR: Pass the whole list item
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
        // REFACTOR: Use source and id from the passed model object
        const data = await getModelDetails(
          selectedModel.source,
          selectedModel.id
        );
        setDetails(data);
      } catch (err: any) {
        setError(err.message || "Fehler beim Laden der Modelldetails.");
      } finally {
        setIsLoading(false);
      }
    };
    fetchDetails();
  }, [selectedModel]); // Dependency is now the whole model object

  const formatFileSize = (bytes?: number | null): string => {
    if (!bytes) return "N/A";
    const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${parseFloat((bytes / Math.pow(1024, i)).toFixed(2))} ${sizes[i]}`;
  };

  if (isLoading)
    return <p className="loading-message">Lade Modelldetails...</p>;
  if (error) return <p className="error-message">{error}</p>;
  if (!details)
    return <p className="no-results-message">Modelldetails nicht gefunden.</p>;

  return (
    <div className="model-details-page">
      <div className="details-page-header">
        <button onClick={onBack} className="back-button">
          <ArrowLeft size={18} /> Zurück
        </button>
        <header>
          <h1>{details.model_name}</h1>
          <p>von: {details.author}</p>
        </header>
      </div>

      <div className="details-content-wrapper">
        <section className="details-section files-section">
          <h2>Dateien ({details.siblings?.length || 0})</h2>
          <ul className="files-list">
            {details.siblings?.map((file) => (
              <li key={file.rfilename} className="file-item">
                <span>
                  {file.rfilename} ({formatFileSize(file.size)})
                </span>
                <button
                  onClick={() => openDownloadModal(details, file)}
                  className="button-icon"
                >
                  <Download size={18} />
                </button>
              </li>
            ))}
          </ul>
        </section>

        <section className="details-section readme-section">
          <h2>README.md</h2>
          <div className="readme-content">
            <ReactMarkdown>
              {details.readme_content || "Kein README verfügbar."}
            </ReactMarkdown>
          </div>
        </section>
      </div>
    </div>
  );
};

export default ModelDetailsPage;

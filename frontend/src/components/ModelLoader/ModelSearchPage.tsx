// frontend/src/components/ModelLoader/ModelSearchPage.tsx
import React, { useState, useCallback, useEffect } from "react";
import {
  searchModels,
  getModelDetails,
  type SearchModelParams,
  type ModelListItem, // REFACTOR: Generic type
  type PaginatedModelListResponse,
  type ModelDetails, // REFACTOR: Generic type
} from "../../api/api";
import { Download, Info, Loader2 } from "lucide-react";

interface ModelSearchPageProps {
  onModelSelect: (model: ModelListItem) => void;
  openDownloadModal: (modelDetails: ModelDetails) => void;
  isConfigurationDone: boolean;
}

const ModelSearchPage: React.FC<ModelSearchPageProps> = ({
  onModelSelect,
  openDownloadModal,
  isConfigurationDone,
}) => {
  const [searchParams, setSearchParams] = useState<SearchModelParams>({
    source: "huggingface", // Default source
    search: "",
    author: "",
    tags: [],
    sort: "lastModified",
    direction: -1,
    limit: 25,
    page: 1,
  });
  const [results, setResults] = useState<ModelListItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isFetchingDetails, setIsFetchingDetails] = useState<string | null>(
    null
  );
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState<boolean>(false);
  const [currentPage, setCurrentPage] = useState<number>(1);

  const performSearch = useCallback(
    async (pageToLoad: number, isNewSearch: boolean = false) => {
      setIsLoading(true);
      setError(null);
      if (isNewSearch) {
        setResults([]);
        setCurrentPage(1);
        pageToLoad = 1;
      }
      try {
        const response: PaginatedModelListResponse = await searchModels({
          ...searchParams,
          page: pageToLoad,
        });
        setResults((prev) =>
          isNewSearch ? response.items : [...prev, ...response.items]
        );
        setHasMore(response.has_more);
        setCurrentPage(pageToLoad);
      } catch (err) {
        setError("Fehler bei der Suche nach Modellen.");
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    },
    [searchParams]
  );

  // Effect to trigger search on filter/sort changes
  useEffect(() => {
    const handler = setTimeout(() => {
      performSearch(1, true);
    }, 500); // Debounce search
    return () => clearTimeout(handler);
  }, [
    searchParams.search,
    searchParams.author,
    searchParams.tags,
    searchParams.sort,
    searchParams.direction,
    performSearch,
  ]);

  const handleInputChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    const { name, value } = e.target;
    setSearchParams((prev) => ({
      ...prev,
      page: 1, // Reset page on any filter change
      [name]:
        name === "tags"
          ? value
              .split(",")
              .map((t) => t.trim())
              .filter(Boolean)
          : value,
    }));
  };

  const handleLoadMore = () => {
    if (hasMore && !isLoading) {
      performSearch(currentPage + 1);
    }
  };

  const handleDirectDownloadClick = async (
    e: React.MouseEvent,
    model: ModelListItem
  ) => {
    e.stopPropagation();
    if (!isConfigurationDone) {
      alert("Bitte zuerst den Basispfad in den Einstellungen konfigurieren.");
      return;
    }
    setIsFetchingDetails(model.id);
    setError(null);
    try {
      // REFACTOR: Pass source and id to getModelDetails
      const details = await getModelDetails(model.source, model.id);
      if (details) {
        openDownloadModal(details);
      } else {
        setError(`Details für ${model.id} konnten nicht geladen werden.`);
      }
    } catch (err: any) {
      setError(`Fehler beim Laden der Details für ${model.id}: ${err.message}`);
    } finally {
      setIsFetchingDetails(null);
    }
  };

  return (
    <div className="model-search-page">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          performSearch(1, true);
        }}
        className="search-form"
      >
        {/* Search and filter inputs... */}
        <div className="form-row">
          <input
            type="text"
            name="search"
            placeholder="Modell suchen..."
            value={searchParams.search}
            onChange={handleInputChange}
            className="search-input-main"
          />
        </div>
        {/* ... other inputs like author, tags, sort ... */}
      </form>

      {error && <p className="error-message">{error}</p>}

      <div className="search-results-container">
        {results.map((model) => (
          <div key={model.id} className="result-item">
            <div className="result-item-info">
              <h3>{model.model_name}</h3>
              <p className="author-info">
                von: {model.author || "Unbekannt"} ({model.source})
              </p>
            </div>
            <div className="result-item-actions">
              <button
                onClick={() => onModelSelect(model)}
                className="button-icon"
                title="Details anzeigen"
              >
                <Info size={18} />
              </button>
              <button
                onClick={(e) => handleDirectDownloadClick(e, model)}
                className="button-icon"
                disabled={
                  !isConfigurationDone || isFetchingDetails === model.id
                }
                title="Dateien herunterladen"
              >
                {isFetchingDetails === model.id ? (
                  <Loader2 size={18} className="animate-spin" />
                ) : (
                  <Download size={18} />
                )}
              </button>
            </div>
          </div>
        ))}
        {isLoading && <p className="loading-message">Lade...</p>}
        {hasMore && !isLoading && (
          <button onClick={handleLoadMore} className="load-more-button">
            Mehr laden
          </button>
        )}
      </div>
    </div>
  );
};

export default ModelSearchPage;

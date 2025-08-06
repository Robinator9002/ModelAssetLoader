// frontend/src/components/ModelLoader/ModelSearchPage.tsx
import React, { useState, useCallback, useEffect, useRef } from 'react';
import {
    searchModels,
    getModelDetails,
    type SearchModelParams,
    type ModelListItem,
    type PaginatedModelListResponse,
    // --- FIX: Removed unused ModelDetails import ---
} from '../../api/api';
// --- REFACTOR: Import the new modal store ---
import { useModalStore } from '../../state/modalStore';
// --- REFACTOR: Import the config store to check configuration status ---
import { useConfigStore } from '../../state/configStore';
// --- FIX: Added missing AlertTriangle import ---
import { Download, Info, Loader2, ChevronDown, ArrowUp, AlertTriangle } from 'lucide-react';

interface ModelSearchPageProps {
    onModelSelect: (model: ModelListItem) => void;
}

/**
 * @refactor This component is now decoupled from App.tsx for modal control.
 * It uses the `useModalStore` to open the download modal directly and the
 * `useConfigStore` to check if the application is configured.
 */
const ModelSearchPage: React.FC<ModelSearchPageProps> = ({ onModelSelect }) => {
    // --- State from Zustand Stores ---
    const { openDownloadModal } = useModalStore();
    const { pathConfig } = useConfigStore();
    const isConfigurationDone = !!pathConfig.basePath;

    // --- Local Component State ---
    const [searchParams, setSearchParams] = useState<SearchModelParams>({
        source: 'huggingface',
        search: '',
        author: '',
        tags: [],
        sort: 'lastModified',
        direction: -1,
        limit: 25,
        page: 1,
    });
    const [results, setResults] = useState<ModelListItem[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [isLoadingMore, setIsLoadingMore] = useState<boolean>(false);
    const [isFetchingDetails, setIsFetchingDetails] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [hasMore, setHasMore] = useState<boolean>(false);
    const [currentPage, setCurrentPage] = useState<number>(1);
    const [showScrollTop, setShowScrollTop] = useState(false);

    const resultsContainerRef = useRef<HTMLDivElement>(null);

    // --- Data Fetching ---
    const performSearch = useCallback(
        async (pageToLoad: number, isNewSearch: boolean = false) => {
            if (isNewSearch) {
                setIsLoading(true);
                setResults([]);
            } else {
                setIsLoadingMore(true);
            }
            setError(null);

            try {
                const response: PaginatedModelListResponse = await searchModels({
                    ...searchParams,
                    page: pageToLoad,
                });

                if (response.items) {
                    setResults((prev) =>
                        isNewSearch ? response.items : [...prev, ...response.items],
                    );
                    setHasMore(response.has_more);
                    setCurrentPage(pageToLoad);
                } else {
                    throw new Error('Invalid response from server.');
                }
            } catch (err) {
                setError('Failed to search for models. Please try again later.');
                console.error(err);
            } finally {
                setIsLoading(false);
                setIsLoadingMore(false);
            }
        },
        [searchParams],
    );

    // --- Effects ---
    useEffect(() => {
        const handler = setTimeout(() => {
            performSearch(1, true);
        }, 500);
        return () => clearTimeout(handler);
    }, [
        searchParams.search,
        searchParams.author,
        searchParams.tags,
        searchParams.sort,
        searchParams.direction,
        performSearch,
    ]);

    // --- Event Handlers ---
    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        const { name, value } = e.target;
        setSearchParams((prev) => ({
            ...prev,
            page: 1,
            [name]:
                name === 'tags'
                    ? value
                          .split(',')
                          .map((t) => t.trim())
                          .filter(Boolean)
                    : name === 'direction'
                    ? parseInt(value, 10)
                    : value,
        }));
    };

    const handleLoadMore = () => {
        if (hasMore && !isLoading && !isLoadingMore) {
            performSearch(currentPage + 1);
        }
    };

    const handleDirectDownloadClick = async (e: React.MouseEvent, model: ModelListItem) => {
        e.stopPropagation();
        if (!isConfigurationDone) {
            alert('Please configure the base path in the settings first.');
            return;
        }
        setIsFetchingDetails(model.id);
        setError(null);
        try {
            const details = await getModelDetails(model.source, model.id);
            if (details) {
                openDownloadModal(details);
            } else {
                throw new Error(`Could not load details for ${model.id}.`);
            }
        } catch (err: any) {
            setError(`Error fetching details for ${model.id}: ${err.message}`);
        } finally {
            setIsFetchingDetails(null);
        }
    };

    const handleScroll = () => {
        if (resultsContainerRef.current) {
            setShowScrollTop(resultsContainerRef.current.scrollTop > 300);
        }
    };

    const scrollToTop = () => {
        resultsContainerRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
    };

    // --- Render Logic ---
    return (
        <div className="model-search-page">
            <form
                onSubmit={(e) => {
                    e.preventDefault();
                    performSearch(1, true);
                }}
                className="search-form"
            >
                <div className="form-row">
                    <input
                        type="text"
                        name="search"
                        placeholder="Search for models..."
                        value={searchParams.search || ''}
                        onChange={handleInputChange}
                        className="search-input-main"
                    />
                </div>
                <div className="form-row" style={{ gap: '1rem' }}>
                    <div className="form-group" style={{ flex: '1' }}>
                        <label htmlFor="sort-by">Sort By</label>
                        <select
                            id="sort-by"
                            name="sort"
                            value={searchParams.sort}
                            onChange={handleInputChange}
                            className="config-select"
                        >
                            <option value="lastModified">Last Modified</option>
                            <option value="downloads">Downloads</option>
                            <option value="likes">Likes</option>
                        </select>
                    </div>
                    <div className="form-group" style={{ flex: '1' }}>
                        <label htmlFor="sort-direction">Direction</label>
                        <select
                            id="sort-direction"
                            name="direction"
                            value={searchParams.direction}
                            onChange={handleInputChange}
                            className="config-select"
                        >
                            <option value={-1}>Descending</option>
                            <option value={1}>Ascending</option>
                        </select>
                    </div>
                </div>
            </form>

            <div
                className="search-results-container"
                ref={resultsContainerRef}
                onScroll={handleScroll}
            >
                {isLoading ? (
                    <div className="page-state-container">
                        <Loader2 size={32} className="animate-spin" />
                        <p>Searching for models...</p>
                    </div>
                ) : error ? (
                    <div className="page-state-container">
                        <AlertTriangle size={32} className="icon-error" />
                        <p>{error}</p>
                    </div>
                ) : results.length === 0 ? (
                    <div className="page-state-container">
                        <p>No models found. Try adjusting your search terms.</p>
                    </div>
                ) : (
                    <>
                        {results.map((model) => (
                            <div
                                key={model.id}
                                className="result-item"
                                onClick={() => onModelSelect(model)}
                            >
                                <div className="result-item-info">
                                    <h3>{model.model_name}</h3>
                                    <p className="author-info">
                                        by: {model.author || 'Unknown'} (Source: {model.source})
                                    </p>
                                </div>
                                <div className="result-item-actions">
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            onModelSelect(model);
                                        }}
                                        className="button-icon"
                                        title="View Details"
                                    >
                                        <Info size={18} />
                                    </button>
                                    <button
                                        onClick={(e) => handleDirectDownloadClick(e, model)}
                                        className="button-icon"
                                        disabled={
                                            !isConfigurationDone || isFetchingDetails === model.id
                                        }
                                        title="Download Files"
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
                        {hasMore && (
                            <button
                                onClick={handleLoadMore}
                                className="button button-primary load-more-button"
                                disabled={isLoadingMore}
                            >
                                {isLoadingMore ? (
                                    <Loader2 size={20} className="animate-spin" />
                                ) : (
                                    <ChevronDown size={20} />
                                )}
                                Load More
                            </button>
                        )}
                    </>
                )}
                <button
                    className={`scroll-to-top-button ${showScrollTop ? 'visible' : ''}`}
                    onClick={scrollToTop}
                    title="Scroll to top"
                >
                    <ArrowUp size={20} />
                </button>
            </div>
        </div>
    );
};

export default ModelSearchPage;

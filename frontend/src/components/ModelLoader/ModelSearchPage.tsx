// frontend/src/components/ModelLoader/ModelSearchPage.tsx
import React from 'react';
// --- REFACTOR: Import the new custom hook ---
import { useModelSearch } from './useModelSearch';

// --- Component & Icon Imports ---
import { type ModelListItem } from '~/api';
import { Download, Info, Loader2, ChevronDown, ArrowUp, AlertTriangle } from 'lucide-react';

interface ModelSearchPageProps {
    onModelSelect: (model: ModelListItem) => void;
}

/**
 * @refactor This component has been completely refactored to be a "presentational"
 * or "dumb" component. All of its complex state management, data fetching, and
 * event handling logic has been extracted into the `useModelSearch` custom hook.
 *
 * The component's sole responsibility is now to render the UI based on the state
 * and functions provided by the hook, making it significantly cleaner and more
 * focused on the view layer.
 */
const ModelSearchPage: React.FC<ModelSearchPageProps> = ({ onModelSelect }) => {
    // --- REFACTOR: All logic is now encapsulated in this single hook call ---
    const {
        searchParams,
        results,
        isLoading,
        isLoadingMore,
        isFetchingDetails,
        error,
        hasMore,
        isConfigurationDone,
        showScrollTop,
        resultsContainerRef,
        handleInputChange,
        performSearch,
        handleLoadMore,
        handleDirectDownloadClick,
        handleScroll,
        scrollToTop,
    } = useModelSearch();

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

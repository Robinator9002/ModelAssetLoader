// frontend/src/components/ModelLoader/useModelSearch.tsx
import React, { useState, useCallback, useEffect, useRef } from 'react';
import {
    searchModels,
    getModelDetails,
    type SearchModelParams,
    type ModelListItem,
    type PaginatedModelListResponse,
} from '~/api';
import { useModalStore } from '../state/modalStore';
import { useConfigStore } from '../state/configStore';

/**
 * @hook useModelSearch
 *
 * @description
 * This custom hook encapsulates all the business logic for the model search page.
 * It manages search parameters, fetches and paginates results, handles loading
 * and error states, and triggers the download modal.
 *
 * By extracting this logic, the `ModelSearchPage` component becomes a pure
 * presentational component, focused solely on rendering the UI.
 *
 * @returns An object containing all state and action handlers for the search page.
 */
export const useModelSearch = () => {
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
            } catch (err: any) {
                setError(err.message || 'Failed to search for models. Please try again later.');
                console.error(err);
            } finally {
                setIsLoading(false);
                setIsLoadingMore(false);
            }
        },
        [searchParams],
    );

    // --- Effects ---
    // Debounced search effect
    useEffect(() => {
        const handler = setTimeout(() => {
            performSearch(1, true);
        }, 500); // Debounce search requests by 500ms
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
            page: 1, // Reset to first page on any filter change
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
            // In a real app, you might use a toast notification here.
            alert('Please configure the base path in the settings first.');
            return;
        }
        setIsFetchingDetails(model.id);
        setError(null);
        try {
            const details = await getModelDetails(model.source, model.id);
            openDownloadModal(details);
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

    // --- Return Value ---
    return {
        // State
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
        // Actions
        handleInputChange,
        performSearch,
        handleLoadMore,
        handleDirectDownloadClick,
        handleScroll,
        scrollToTop,
    };
};

// frontend/src/components/FileManager/useFileManager.tsx
import { useState, useEffect, useCallback } from 'react';
import {
    // API functions for file management
    listManagedFilesAPI,
    deleteManagedItemAPI,
    // Type definitions
    type LocalFileItem,
    type ViewMode,
} from '~/api';
import { useConfigStore } from '../state/configStore';

/**
 * @hook useFileManager
 *
 * @description
 * This custom hook encapsulates all the business logic, state management, and
 * API interactions for the file manager feature. It handles fetching files,
 * navigation, deletion, previews, and view mode switching.
 *
 * By extracting this logic from the `FileManagerPage` component, we achieve a
 * clean separation of concerns:
 * - The hook manages *how* the file manager works (the logic).
 * - The component manages *what* the file manager looks like (the JSX).
 *
 * This makes both the logic and the presentation easier to understand,
 * maintain, and test independently.
 *
 * @returns An object containing all the state and action handlers needed by the
 * `FileManagerPage` component to render the UI.
 */
export const useFileManager = () => {
    // --- State from Zustand Store ---
    const { pathConfig, isLoading: isConfigLoading } = useConfigStore();
    const isConfigurationDone = !!pathConfig.basePath;

    // --- Local Component State ---
    const [items, setItems] = useState<LocalFileItem[]>([]);
    const [currentPath, setCurrentPath] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [viewMode, setViewMode] = useState<ViewMode>('models');
    const [itemToDelete, setItemToDelete] = useState<LocalFileItem | null>(null);
    const [itemToPreview, setItemToPreview] = useState<LocalFileItem | null>(null);

    // --- Core Data Fetching Logic ---
    const fetchFiles = useCallback(
        async (path: string | null, mode: ViewMode) => {
            if (!isConfigurationDone) {
                setIsLoading(false);
                return;
            }
            setIsLoading(true);
            setError(null);
            try {
                const response = await listManagedFilesAPI(path, mode);
                setItems(response.items);
                setCurrentPath(response.path);
            } catch (err: any) {
                setError(err.message || 'Failed to load files. Is the backend running?');
                setItems([]);
            } finally {
                setIsLoading(false);
            }
        },
        [isConfigurationDone],
    );

    // --- Effects ---
    // Initial fetch and re-fetch when viewMode or configuration status changes.
    useEffect(() => {
        // Reset path to root when view mode changes
        fetchFiles(null, viewMode);
    }, [viewMode, fetchFiles]);

    // Re-fetch from root if the configuration is completed after initial load
    useEffect(() => {
        if (isConfigurationDone) {
            fetchFiles(null, viewMode);
        }
    }, [isConfigurationDone]); // Only depends on this boolean flag

    // --- Action Handlers ---
    const handleNavigate = (item: LocalFileItem) => {
        if (item.item_type === 'directory') {
            fetchFiles(item.path, viewMode);
        } else {
            setItemToPreview(item);
        }
    };

    const navigateUp = () => {
        if (!currentPath) return;
        const parts = currentPath.replace(/\\/g, '/').split('/');
        const parentPath = parts.slice(0, -1).join('/');
        fetchFiles(parentPath || null, viewMode);
    };

    const navigateHome = () => {
        fetchFiles(null, viewMode);
    };

    const handleRefresh = () => {
        fetchFiles(currentPath, viewMode);
    };

    const handleDeleteRequest = (item: LocalFileItem) => {
        setItemToDelete(item);
    };

    const handleConfirmDelete = async () => {
        if (!itemToDelete) return;
        try {
            await deleteManagedItemAPI(itemToDelete.path);
            handleRefresh(); // Refresh the view after deletion
        } catch (err: any) {
            setError(`Failed to delete ${itemToDelete.name}: ${err.message}`);
        } finally {
            setItemToDelete(null);
        }
    };

    // --- Return Value ---
    // Expose all state and actions needed by the component.
    return {
        // State
        items,
        currentPath,
        isLoading: isLoading || isConfigLoading,
        error,
        viewMode,
        itemToDelete,
        itemToPreview,
        isConfigurationDone,
        // Actions
        setViewMode,
        handleNavigate,
        navigateUp,
        navigateHome,
        handleRefresh,
        handleDeleteRequest,
        handleConfirmDelete,
        setItemToDelete, // Expose setter to allow closing the modal from the component
        setItemToPreview, // Expose setter for closing the preview
    };
};

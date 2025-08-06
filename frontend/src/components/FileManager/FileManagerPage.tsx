// frontend/src/components/FileManager/FileManagerPage.tsx
import React, { useState, useEffect, useCallback } from 'react';
import {
    // --- REFACTOR: Import API functions directly ---
    listManagedFilesAPI,
    deleteManagedItemAPI,
    type LocalFileItem,
    type ViewMode,
} from '../../api/api';
// --- REFACTOR: Import Zustand store to get config state ---
import { useConfigStore } from '../../state/configStore';
import { Loader2, AlertTriangle, ArrowLeft, RefreshCw, Home, Info } from 'lucide-react';
import FileItem from './FileItem';
import ConfirmModal from '../Layout/ConfirmModal';
import FilePreview from './FilePreview';
import ViewModeSwitcher from './ViewModeSwitcher';

/**
 * @refactor This component is now self-sufficient. It fetches its own configuration
 * state from the `useConfigStore` and manages all its internal state and API calls
 * for file management, completely decoupling it from App.tsx.
 */
const FileManagerPage: React.FC = () => {
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
                // Don't attempt to fetch if the base path isn't set.
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
    ); // Re-run if config status changes

    // --- Effects ---
    // Initial fetch and re-fetch when viewMode or configuration status changes.
    useEffect(() => {
        fetchFiles(null, viewMode);
    }, [viewMode, fetchFiles, isConfigurationDone]);

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
        // Improved logic for finding the parent path
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

    // --- Render Logic ---

    const renderContent = () => {
        if (isLoading || isConfigLoading) {
            return (
                <div className="page-state-container">
                    <Loader2 size={32} className="animate-spin" />
                    <p>Loading Files...</p>
                </div>
            );
        }

        if (!isConfigurationDone) {
            return (
                <div className="page-state-container">
                    <Info size={32} />
                    <p>The File Manager is not yet configured.</p>
                    <span className="config-hint">
                        Please go to 'Settings' to set your base model path.
                    </span>
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

        if (items.length === 0) {
            return (
                <div className="page-state-container">
                    <p>
                        {viewMode === 'models'
                            ? 'No models found in this directory.'
                            : 'This directory is empty.'}
                    </p>
                </div>
            );
        }

        return (
            <div className="file-list-grid">
                {items.map((item) => (
                    <FileItem
                        key={item.path}
                        item={item}
                        onNavigate={handleNavigate}
                        onDelete={handleDeleteRequest}
                    />
                ))}
            </div>
        );
    };

    return (
        <div className="file-manager-page">
            <div className="file-manager-header">
                <div className="breadcrumb-bar">
                    <button
                        onClick={navigateHome}
                        className="button-icon"
                        title="Go to root"
                        disabled={isLoading || !isConfigurationDone || currentPath === null}
                    >
                        <Home size={18} />
                    </button>
                    {currentPath && (
                        <button
                            onClick={navigateUp}
                            className="button-icon"
                            title="Go up one level"
                            disabled={isLoading || !isConfigurationDone}
                        >
                            <ArrowLeft size={18} />
                        </button>
                    )}
                    <span className="current-path-display">/ {currentPath || ''}</span>
                </div>
                <div className="header-actions">
                    <ViewModeSwitcher currentMode={viewMode} onModeChange={setViewMode} />
                    <button
                        onClick={handleRefresh}
                        className="button-icon"
                        title="Refresh"
                        disabled={isLoading || !isConfigurationDone}
                    >
                        <RefreshCw size={16} className={isLoading ? 'animate-spin' : ''} />
                    </button>
                </div>
            </div>

            <div className="file-manager-content">{renderContent()}</div>

            {itemToDelete && (
                <ConfirmModal
                    isOpen={!!itemToDelete}
                    title={`Delete ${itemToDelete.item_type}`}
                    message={
                        <span>
                            Are you sure you want to permanently delete{' '}
                            <strong>{itemToDelete.name}</strong>? This action cannot be undone.
                        </span>
                    }
                    onConfirm={handleConfirmDelete}
                    onCancel={() => setItemToDelete(null)}
                    confirmText="Yes, Delete"
                    isDanger={true}
                />
            )}

            {itemToPreview && (
                <FilePreview item={itemToPreview} onClose={() => setItemToPreview(null)} />
            )}
        </div>
    );
};

export default FileManagerPage;

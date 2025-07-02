// frontend/src/components/FileManager/FileManagerPage.tsx
import React, { useState, useEffect, useCallback } from 'react';
import { listManagedFilesAPI, deleteManagedItemAPI, type LocalFileItem, type ViewMode } from '../../api/api';
import { Loader2, AlertTriangle, ArrowLeft, RefreshCw, Home } from 'lucide-react';
import FileItem from './FileItem';
import ConfirmModal from '../Layout/ConfirmModal';
import FilePreview from './FilePreview';
import ViewModeSwitcher from './ViewModeSwitcher';

const FileManagerPage: React.FC = () => {
    const [items, setItems] = useState<LocalFileItem[]>([]);
    const [currentPath, setCurrentPath] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [viewMode, setViewMode] = useState<ViewMode>('models');
    
    const [itemToDelete, setItemToDelete] = useState<LocalFileItem | null>(null);
    const [itemToPreview, setItemToPreview] = useState<LocalFileItem | null>(null);

    // This is the core logic update.
    const fetchFiles = useCallback(async (path: string | null, mode: ViewMode) => {
        setIsLoading(true);
        setError(null);
        try {
            // The API now returns the final path and the items at that path.
            const response = await listManagedFilesAPI(path, mode);
            setItems(response.items);
            setCurrentPath(response.path); // Update path based on backend's smart response
        } catch (err: any) {
            setError(err.message || 'Failed to load files. Is the backend running and the base path configured?');
            setItems([]);
        } finally {
            setIsLoading(false);
        }
    }, []);

    // Initial fetch and re-fetch when viewMode changes
    useEffect(() => {
        // When the component loads or viewMode changes, start the smart search from the root.
        fetchFiles(null, viewMode);
    }, [viewMode, fetchFiles]);

    // Navigation now just calls fetchFiles with the new path
    const handleNavigate = (item: LocalFileItem) => {
        if (item.type === 'directory') {
            fetchFiles(item.path, viewMode);
        } else {
            setItemToPreview(item);
        }
    };
    
    const navigateUp = () => {
        if (!currentPath) return;
        const parentPath = currentPath.substring(0, currentPath.lastIndexOf('/'));
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
            handleRefresh();
        } catch (err: any) {
            setError(`Failed to delete ${itemToDelete.name}: ${err.message}`);
        } finally {
            setItemToDelete(null);
        }
    };

    const renderContent = () => {
        if (isLoading) {
            return <div className="loading-message"><Loader2 size={24} className="animate-spin" /><span>Finding models...</span></div>;
        }
        if (error) {
            return <div className="feedback-message error"><AlertTriangle size={16} /><span>{error}</span></div>;
        }
        if (items.length === 0) {
            return <p className="no-results-message">
                {viewMode === 'models'
                    ? 'No relevant models found in the configured base path.'
                    : 'This directory is empty.'
                }
            </p>;
        }
        return (
            <div className="file-list-grid">
                {items.map(item => (
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
                    <button onClick={navigateHome} className="button-icon" title="Go to root" disabled={isLoading || currentPath === null}>
                        <Home size={18} />
                    </button>
                    {currentPath && (
                        <button onClick={navigateUp} className="button-icon" title="Go up one level" disabled={isLoading}>
                            <ArrowLeft size={18} />
                        </button>
                    )}
                    <span className="current-path-display">/ {currentPath || ''}</span>
                </div>
                <div className="header-actions">
                    <ViewModeSwitcher currentMode={viewMode} onModeChange={setViewMode} />
                    <button onClick={handleRefresh} className="button-icon" title="Refresh" disabled={isLoading}>
                        <RefreshCw size={16} className={isLoading ? 'animate-spin' : ''} />
                    </button>
                </div>
            </div>

            <div className="file-manager-content">
                {renderContent()}
            </div>

            {itemToDelete && (
                <ConfirmModal
                    isOpen={!!itemToDelete}
                    title={`Delete ${itemToDelete.type}`}
                    message={<span>Are you sure you want to permanently delete <strong>{itemToDelete.name}</strong>? This action cannot be undone.</span>}
                    onConfirm={handleConfirmDelete}
                    onCancel={() => setItemToDelete(null)}
                    confirmText="Yes, Delete"
                    isDanger={true}
                />
            )}

            {itemToPreview && (
                <FilePreview
                    item={itemToPreview}
                    onClose={() => setItemToPreview(null)}
                />
            )}
        </div>
    );
};

export default FileManagerPage;

// frontend/src/components/FileManager/FileManagerPage.tsx
import React, { useState, useEffect } from 'react';
import { listManagedFilesAPI, deleteManagedItemAPI, type LocalFileItem, type ViewMode } from '../../api/api';
import { Loader2, AlertTriangle, ArrowLeft, RefreshCw, Home } from 'lucide-react';
import FileItem from './FileItem';
import ConfirmModal from '../Layout/ConfirmModal';
import FilePreview from './FilePreview';
import ViewModeSwitcher from './ViewModeSwitcher';

const FileManagerPage: React.FC = () => {
    // State now holds the items exactly as received from the API
    const [items, setItems] = useState<LocalFileItem[]>([]);
    const [currentPath, setCurrentPath] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [viewMode, setViewMode] = useState<ViewMode>('models');
    
    // Imperative trigger for refreshing the view
    const [refreshTrigger, setRefreshTrigger] = useState(0);

    const [itemToDelete, setItemToDelete] = useState<LocalFileItem | null>(null);
    const [itemToPreview, setItemToPreview] = useState<LocalFileItem | null>(null);

    // Centralized data fetching logic in a single useEffect hook
    useEffect(() => {
        const fetchFiles = async () => {
            setIsLoading(true);
            setError(null);
            try {
                // Pass the current path and view mode directly to the API
                const fileList = await listManagedFilesAPI(currentPath, viewMode);
                setItems(fileList);
            } catch (err: any) {
                setError(err.message || 'Failed to load files. Is the backend running and the base path configured?');
                setItems([]); // Clear items on error
            } finally {
                setIsLoading(false);
            }
        };

        fetchFiles();
    }, [currentPath, viewMode, refreshTrigger]); // Re-fetches when path, mode, or trigger changes

    // Navigation functions now just update the path, triggering the effect
    const handleNavigate = (item: LocalFileItem) => {
        if (item.type === 'directory') {
            setCurrentPath(item.path);
        } else {
            setItemToPreview(item);
        }
    };

    const navigateUp = () => {
        if (!currentPath) return;
        const parentPath = currentPath.substring(0, currentPath.lastIndexOf('/'));
        setCurrentPath(parentPath || null);
    };

    const navigateHome = () => {
        setCurrentPath(null);
    };
    
    const handleRefresh = () => {
        setRefreshTrigger(c => c + 1);
    };

    const handleDeleteRequest = (item: LocalFileItem) => {
        setItemToDelete(item);
    };

    const handleConfirmDelete = async () => {
        if (!itemToDelete) return;
        
        try {
            await deleteManagedItemAPI(itemToDelete.path);
            handleRefresh(); // Trigger a refresh after successful deletion
        } catch (err: any) {
            console.error("Delete failed:", err);
            setError(`Failed to delete ${itemToDelete.name}: ${err.message}`);
        } finally {
            setItemToDelete(null);
        }
    };

    const renderContent = () => {
        if (isLoading) {
            return <div className="loading-message"><Loader2 size={24} className="animate-spin" /><span>Loading items...</span></div>;
        }
        if (error) {
            return <div className="feedback-message error"><AlertTriangle size={16} /><span>{error}</span></div>;
        }
        if (items.length === 0) {
            return <p className="no-results-message">
                {viewMode === 'models'
                    ? 'No relevant models or folders found.'
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
                    <button onClick={navigateHome} className="button-icon" title="Go to root" disabled={isLoading}>
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

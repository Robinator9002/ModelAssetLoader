// frontend/src/components/FileManager/FileManagerPage.tsx
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { listManagedFilesAPI, deleteManagedItemAPI, type LocalFileItem } from '../../api/api';
import { Loader2, AlertTriangle, ArrowLeft, RefreshCw, Home } from 'lucide-react';
import FileItem from './FileItem';
import ConfirmModal from '../Layout/ConfirmModal';
import FilePreview from './FilePreview';
import ViewModeSwitcher, { type ViewMode } from './ViewModeSwitcher';

// List of typical model file extensions for the 'Models' view
const MODEL_FILE_EXTENSIONS = [
    '.safetensors', '.ckpt', '.pt', '.bin', '.pth', '.onnx'
];

const FileManagerPage: React.FC = () => {
    const [allItems, setAllItems] = useState<LocalFileItem[]>([]);
    const [currentPath, setCurrentPath] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [viewMode, setViewMode] = useState<ViewMode>('models');

    const [itemToDelete, setItemToDelete] = useState<LocalFileItem | null>(null);
    const [itemToPreview, setItemToPreview] = useState<LocalFileItem | null>(null);

    const fetchFiles = useCallback(async (path: string | null) => {
        setIsLoading(true);
        setError(null);
        try {
            const fileList = await listManagedFilesAPI(path);
            setAllItems(fileList);
            setCurrentPath(path);
        } catch (err: any) {
            setError(err.message || 'Failed to load files. Is the backend running and the base path configured?');
            setAllItems([]);
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchFiles(null);
    }, [fetchFiles]);

    // Use useMemo to efficiently filter items based on the view mode
    const displayedItems = useMemo(() => {
        if (viewMode === 'explorer') {
            return allItems;
        }
        // 'models' view logic
        return allItems.filter(item => {
            if (item.type === 'directory') {
                return true; // Always show directories
            }
            // For files, check if the extension is in our allowed list
            return MODEL_FILE_EXTENSIONS.some(ext => item.name.toLowerCase().endsWith(ext));
        });
    }, [allItems, viewMode]);

    const handleNavigate = (item: LocalFileItem) => {
        if (item.type === 'directory') {
            fetchFiles(item.path);
        } else {
            setItemToPreview(item);
        }
    };

    const navigateUp = () => {
        if (!currentPath) return;
        const parentPath = currentPath.substring(0, currentPath.lastIndexOf('/'));
        fetchFiles(parentPath || null);
    };

    const navigateHome = () => {
        fetchFiles(null);
    };

    const handleDeleteRequest = (item: LocalFileItem) => {
        setItemToDelete(item);
    };

    const handleConfirmDelete = async () => {
        if (!itemToDelete) return;
        
        try {
            await deleteManagedItemAPI(itemToDelete.path);
            fetchFiles(currentPath);
        } catch (err: any) {
            console.error("Delete failed:", err);
            setError(`Failed to delete ${itemToDelete.name}: ${err.message}`);
        } finally {
            setItemToDelete(null);
        }
    };

    const renderContent = () => {
        if (isLoading) {
            return <div className="loading-message"><Loader2 size={24} className="animate-spin" /><span>Loading files...</span></div>;
        }
        if (error) {
            return <div className="feedback-message error"><AlertTriangle size={16} /><span>{error}</span></div>;
        }
        if (displayedItems.length === 0) {
            return <p className="no-results-message">
                {viewMode === 'models' && allItems.length > 0
                    ? 'No model files found in this directory.'
                    : 'This directory is empty.'
                }
            </p>;
        }
        return (
            <div className="file-list-grid">
                {displayedItems.map(item => (
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
                    <button onClick={() => fetchFiles(currentPath)} className="button-icon" title="Refresh" disabled={isLoading}>
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

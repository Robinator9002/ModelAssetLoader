// frontend/src/components/FileManager/FileManagerPage.tsx
import React from 'react';
// --- REFACTOR: Import the new custom hook ---
import { useFileManager } from './useFileManager';

// --- Component & Icon Imports ---
import { Loader2, AlertTriangle, ArrowLeft, RefreshCw, Home, Info } from 'lucide-react';
import FileItem from './FileItem';
import ConfirmModal from '../Layout/ConfirmModal';
import FilePreview from './FilePreview';
import ViewModeSwitcher from '../Switchers/ViewModeSwitcher';

/**
 * @refactor This component has been completely refactored to be a "presentational"
 * or "dumb" component. All of its complex state management, data fetching, and
 * event handling logic has been extracted into the `useFileManager` custom hook.
 *
 * The component's sole responsibility is now to render the UI based on the state
 * and functions provided by the hook. This makes the component significantly
 * cleaner, easier to read, and focused only on the view layer.
 */
const FileManagerPage: React.FC = () => {
    // --- REFACTOR: All logic is now encapsulated in this single hook call ---
    const {
        items,
        currentPath,
        isLoading,
        error,
        viewMode,
        itemToDelete,
        itemToPreview,
        isConfigurationDone,
        setViewMode,
        handleNavigate,
        navigateUp,
        navigateHome,
        handleRefresh,
        handleDeleteRequest,
        handleConfirmDelete,
        setItemToDelete,
        setItemToPreview,
    } = useFileManager();

    // --- Render Logic ---
    // This helper function determines what to display in the main content area.
    const renderContent = () => {
        if (isLoading) {
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

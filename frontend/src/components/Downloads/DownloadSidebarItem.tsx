// frontend/src/components/Downloads/DownloadSidebarItem.tsx
import React, { useState } from 'react';
import { Loader2, CheckCircle2, AlertTriangle, X, Ban, Play } from 'lucide-react';
import { cancelDownloadAPI, cancelUiTaskAPI, stopUiAPI, type DownloadStatus } from '../../api/api';
import ConfirmModal from '../Layout/ConfirmModal';

interface DownloadSidebarItemProps {
    status: DownloadStatus;
    onDismiss: (downloadId: string) => void;
}

const DownloadSidebarItem: React.FC<DownloadSidebarItemProps> = ({ status, onDismiss }) => {
    const {
        download_id,
        filename,
        status: taskStatus,
        progress,
        error_message,
        repo_id,
        status_text,
    } = status;

    const [isConfirmOpen, setIsConfirmOpen] = useState(false);

    const isCancellable =
        taskStatus === 'pending' || taskStatus === 'downloading' || taskStatus === 'running';
    const isUiTask = repo_id === 'UI Installation' || repo_id === 'UI Adoption Repair';
    const isUiProcess = repo_id === 'UI Process';

    const getStatusIcon = () => {
        switch (taskStatus) {
            case 'downloading':
                return <Loader2 size={18} className="animate-spin" />;
            case 'running':
                return <Play size={18} className="icon-running" />;
            case 'completed':
                return <CheckCircle2 size={18} className="icon-success" />;
            case 'cancelled':
                return <Ban size={18} className="icon-cancelled" />;
            case 'error':
                return <AlertTriangle size={18} className="icon-error" />;
            default: // pending
                return <Loader2 size={18} className="animate-spin icon-pending" />;
        }
    };

    const handleRequestCancel = () => {
        setIsConfirmOpen(true);
    };

    const handleConfirmCancel = async () => {
        try {
            if (isUiProcess && taskStatus === 'running') {
                await stopUiAPI(download_id);
            } else if (isUiTask) {
                await cancelUiTaskAPI(download_id);
            } else {
                await cancelDownloadAPI(download_id);
            }
        } catch (error) {
            console.error(`Failed to stop/cancel task ${download_id}:`, error);
        } finally {
            setIsConfirmOpen(false);
        }
    };

    const handleActionClick = () => {
        if (isCancellable) {
            handleRequestCancel();
        } else {
            onDismiss(download_id);
        }
    };

    const confirmModalTitle =
        isUiProcess && taskStatus === 'running' ? 'Stop Process?' : 'Cancel Task?';
    const confirmModalMessage =
        isUiProcess && taskStatus === 'running'
            ? `Are you sure you want to stop the running process for "${filename}"?`
            : `Are you sure you want to cancel the task for "${filename}"? This cannot be undone.`;
    const confirmText = isUiProcess && taskStatus === 'running' ? 'Yes, Stop' : 'Yes, Cancel';

    const showStatusText = isUiTask && status_text && taskStatus !== 'completed';

    const renderBody = () => {
        if (taskStatus === 'error') {
            return (
                <div
                    className="download-item-error-message"
                    title={error_message || 'An error occurred.'}
                >
                    {error_message || 'An unknown error occurred.'}
                </div>
            );
        }
        if (taskStatus === 'cancelled') {
            return (
                <div
                    className="download-item-error-message"
                    title={error_message || 'Task was cancelled.'}
                >
                    {error_message || 'The task was cancelled by the user.'}
                </div>
            );
        }
        if (taskStatus === 'running' && isUiProcess) {
            return (
                <div className="running-process-display">
                    <div className="running-indicator">
                        <span></span>
                        <span></span>
                        <span></span>
                        <span></span>
                        <span></span>
                    </div>
                    <div className="download-item-status-text">Process is Active</div>
                </div>
            );
        }
        // Default display for downloads and installations
        return (
            <div className="progress-display">
                {showStatusText && (
                    <div className="download-item-status-text" title={status_text!}>
                        {status_text}
                    </div>
                )}
                <div className="progress-bar-container">
                    <div
                        className={`progress-bar ${taskStatus}`}
                        style={{ width: `${progress}%` }}
                    />
                    <span className="progress-text">{progress?.toFixed(1) || '0.0'}%</span>
                </div>
            </div>
        );
    };

    return (
        <>
            <div className={`download-sidebar-item ${taskStatus}`} role="alert">
                <div className="download-item-header">
                    <span className="download-item-status-icon">{getStatusIcon()}</span>
                    <span className="download-item-filename" title={filename}>
                        {filename}
                    </span>
                </div>
                <div className="download-item-body">{renderBody()}</div>
                <div className="download-item-actions">
                    <button
                        onClick={handleActionClick}
                        className="button-icon dismiss-button"
                        aria-label={isCancellable ? 'Cancel/Stop Task' : 'Dismiss Notification'}
                        title={isCancellable ? 'Cancel/Stop Task' : 'Dismiss Notification'}
                    >
                        <X size={16} />
                    </button>
                </div>
            </div>
            <ConfirmModal
                isOpen={isConfirmOpen}
                title={confirmModalTitle}
                message={confirmModalMessage}
                onConfirm={handleConfirmCancel}
                onCancel={() => setIsConfirmOpen(false)}
                confirmText={confirmText}
                isDanger={true}
            />
        </>
    );
};

export default DownloadSidebarItem;

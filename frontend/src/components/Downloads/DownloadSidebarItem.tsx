// frontend/src/components/Downloads/DownloadSidebarItem.tsx
import React, { useState } from 'react';
import { Loader2, CheckCircle2, AlertTriangle, X, Ban, Play } from 'lucide-react';
import { cancelDownloadAPI, type DownloadStatus, stopUiAPI } from '../../api/api';
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
    const isUiTask = repo_id === 'UI Process' || repo_id === 'UI Installation';

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
            if (isUiTask && taskStatus === 'running') {
                await stopUiAPI(download_id);
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
        isUiTask && taskStatus === 'running' ? 'Stop Process?' : 'Cancel Task?';
    const confirmModalMessage =
        isUiTask && taskStatus === 'running'
            ? `Are you sure you want to stop the running process for "${filename}"?`
            : `Are you sure you want to cancel the task for "${filename}"?`;
    const confirmText = isUiTask && taskStatus === 'running' ? 'Yes, Stop' : 'Yes, Cancel';

    // Determine if we should show the detailed status text
    const showStatusText = isUiTask && status_text && taskStatus !== 'completed';

    return (
        <>
            <div className={`download-sidebar-item ${taskStatus}`} role="alert">
                <div className="download-item-header">
                    <span className="download-item-status-icon">{getStatusIcon()}</span>
                    <span className="download-item-filename" title={filename}>
                        {filename}
                    </span>
                </div>

                <div className="download-item-body">
                    {taskStatus === 'error' ? (
                        <div
                            className="download-item-error-message"
                            title={error_message || 'An error occurred.'}
                        >
                            {error_message || 'An unknown error occurred.'}
                        </div>
                    ) : taskStatus === 'cancelled' ? (
                        <div
                            className="download-item-error-message"
                            title={error_message || 'Task was cancelled.'}
                        >
                            {error_message || 'The task was cancelled by the user.'}
                        </div>
                    ) : (
                        <div className="progress-display">
                            {/* --- FIX: Conditionally render the status text --- */}
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
                            </div>
                            <span className="progress-text">{progress?.toFixed(1) || '0.0'}%</span>
                        </div>
                    )}
                </div>

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

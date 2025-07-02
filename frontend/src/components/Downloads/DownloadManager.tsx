// frontend/src/components/Files/DownloadManager.tsx
import React, { useState, useEffect } from 'react';
import { Loader2, CheckCircle2, AlertTriangle, X, Ban } from 'lucide-react';
import { dismissDownloadAPI, cancelDownloadAPI, type DownloadStatus } from '../../api/api';
import ConfirmModal from '../Layout/ConfirmModal';

interface DownloadItemProps {
    status: DownloadStatus;
    onDismiss: (id: string) => void;
}

const DownloadItem: React.FC<DownloadItemProps> = ({ status, onDismiss }) => {
    const {
        download_id,
        filename,
        status: downloadStatus,
        progress,
        error_message,
    } = status;

    const [isClosing, setIsClosing] = useState(false);
    const [isConfirmOpen, setIsConfirmOpen] = useState(false);
    // State to track what triggered the cancel request ('x' or 'button')
    const [cancelInitiator, setCancelInitiator] = useState<'button' | 'x' | null>(null);

    // This effect handles the auto-dismissal animation for completed/error toasts.
    // I've added a condition to prevent auto-dismissal for user-cancelled items.
    useEffect(() => {
        let timer: NodeJS.Timeout;
        if (downloadStatus === 'completed' || (downloadStatus === 'error' && !error_message?.includes('Cancelled'))) {
            timer = setTimeout(() => {
                setIsClosing(true);
            }, 4000);
        }
        return () => clearTimeout(timer);
    }, [downloadStatus, error_message]);

    const getStatusIcon = () => {
        switch (downloadStatus) {
            case 'downloading':
                return <Loader2 size={18} className="animate-spin" />;
            case 'completed':
                return <CheckCircle2 size={18} className="text-green-500" />;
            case 'error':
                return <AlertTriangle size={18} className="text-red-500" />;
            default: // pending
                return <Loader2 size={18} className="animate-spin text-gray-400" />;
        }
    };

    // This function dismisses a toast from the UI immediately.
    const handleDismissClick = () => {
        setIsClosing(true);
        // The parent component handles the API call to permanently remove it.
        setTimeout(() => onDismiss(download_id), 300);
    };

    // This function opens the confirmation modal.
    const handleRequestCancel = (initiator: 'button' | 'x') => {
        setCancelInitiator(initiator);
        setIsConfirmOpen(true);
    };

    // This is the core logic passed to the confirmation modal.
    const handleConfirmCancel = async () => {
        if (!download_id) throw new Error("Download ID is missing.");
        
        // Call the new cancellation API.
        await cancelDownloadAPI(download_id);
        // The backend will then send a WebSocket update which changes the item's status.
        
        // Based on your request, we return a message only if the 'Cancel' button was used.
        if (cancelInitiator === 'button') {
            return { message: "Download cancellation initiated." };
        }
        // For the 'x' button, we return nothing, so the modal closes instantly.
    };

    const isCancellable = downloadStatus === 'pending' || downloadStatus === 'downloading';

    return (
        <>
            <div
                className={`download-item-toast ${downloadStatus} ${isClosing ? 'closing' : ''}`}
                key={download_id}
                role="alert"
            >
                <div className="download-toast-header">
                    <span className="download-toast-filename" title={filename}>{filename}</span>
                    <span className="download-toast-status-icon">{getStatusIcon()}</span>
                    {/* The 'X' button now has dual functionality */}
                    <button 
                        onClick={isCancellable ? () => handleRequestCancel('x') : handleDismissClick} 
                        className="dismiss-button"
                        aria-label={isCancellable ? "Request cancellation" : "Dismiss notification"}
                    >
                        <X size={16} />
                    </button>
                </div>
                <div className="download-toast-body">
                    {downloadStatus === 'error' ? (
                        <div className="download-toast-error-message" title={error_message || 'Unknown Error'}>
                            {error_message || 'An unknown error has occurred.'}
                        </div>
                    ) : (
                        <>
                            <div className="progress-bar-container">
                                <div
                                    className={`progress-bar ${downloadStatus}`}
                                    style={{ width: `${progress}%` }}
                                    role="progressbar"
                                    aria-valuenow={progress}
                                />
                            </div>
                            <span className="progress-text">{progress?.toFixed(1) || '0.0'}%</span>
                        </>
                    )}
                </div>
                {/* The new, dedicated cancel button */}
                {isCancellable && (
                    <div className="download-toast-actions">
                        <button className="button button-danger button-small" onClick={() => handleRequestCancel('button')}>
                            <Ban size={14} />
                            <span>Cancel Download</span>
                        </button>
                    </div>
                )}
            </div>

            {/* The confirmation modal, rendered conditionally */}
            <ConfirmModal
                isOpen={isConfirmOpen}
                title="Cancel Download?"
                message={`Are you sure you want to cancel the download for "${filename}"? This action cannot be undone.`}
                onConfirm={handleConfirmCancel}
                onCancel={() => setIsConfirmOpen(false)}
                confirmText="Yes, Cancel"
                cancelText="No, Continue"
                isDanger={true}
            />
        </>
    );
};


interface DownloadManagerProps {
    activeDownloads: Map<string, DownloadStatus>;
}

const DownloadManager: React.FC<DownloadManagerProps> = ({ activeDownloads }) => {

    const handleDismiss = (downloadId: string) => {
        dismissDownloadAPI(downloadId).catch(err => {
            console.error("Dismissal failed:", err);
        });
    };

    if (activeDownloads.size === 0) {
        return null;
    }

    const downloadArray = Array.from(activeDownloads.values());

    return (
        <div className="download-manager-container">
            {downloadArray.map(status => (
                <DownloadItem
                    key={status.download_id}
                    status={status}
                    onDismiss={handleDismiss}
                />
            ))}
        </div>
    );
};

export default DownloadManager;

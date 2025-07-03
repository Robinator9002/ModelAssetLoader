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
    const [cancelInitiator, setCancelInitiator] = useState<'button' | 'x' | null>(null);

    // --- Effect now handles 'cancelled' status ---
    useEffect(() => {
        let timer: NodeJS.Timeout;
        // Auto-dismiss for completed or error toasts after a normal delay
        if (downloadStatus === 'completed' || downloadStatus === 'error') {
            timer = setTimeout(() => {
                setIsClosing(true);
            }, 4000);
        }
        // Auto-dismiss for 'cancelled' toasts after a very short delay
        if (downloadStatus === 'cancelled') {
            timer = setTimeout(() => {
                setIsClosing(true);
            }, 4000); // Vanishes after 4 seconds
        }
        return () => clearTimeout(timer);
    }, [downloadStatus]);

    // --- getStatusIcon now handles 'cancelled' ---
    const getStatusIcon = () => {
        switch (downloadStatus) {
            case 'downloading':
                return <Loader2 size={18} className="animate-spin" />;
            case 'completed':
                return <CheckCircle2 size={18} className="text-green-500" />;
            case 'cancelled':
                return <Ban size={18} className="text-gray-500" />;
            case 'error':
                return <AlertTriangle size={18} className="text-red-500" />;
            default: // pending
                return <Loader2 size={18} className="animate-spin text-gray-400" />;
        }
    };

    const handleDismissClick = () => {
        setIsClosing(true);
        setTimeout(() => onDismiss(download_id), 300);
    };

    const handleRequestCancel = (initiator: 'button' | 'x') => {
        setCancelInitiator(initiator);
        setIsConfirmOpen(true);
    };

    const handleConfirmCancel = async () => {
        if (!download_id) throw new Error("Download ID is missing.");
        await cancelDownloadAPI(download_id);
        if (cancelInitiator === 'button') {
            return { message: "Download cancelled." };
        }
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
                    <button 
                        onClick={isCancellable ? () => handleRequestCancel('x') : handleDismissClick} 
                        className="dismiss-button"
                        aria-label={isCancellable ? "Request cancellation" : "Dismiss notification"}
                    >
                        <X size={16} />
                    </button>
                </div>
                <div className="download-toast-body">
                    {downloadStatus === 'error' || downloadStatus === 'cancelled' ? (
                        <div className="download-toast-error-message" title={error_message || 'Download was cancelled'}>
                            {error_message || 'The download was cancelled by the user.'}
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
                {isCancellable && (
                    <div className="download-toast-actions">
                        <button className="button button-danger button-small" onClick={() => handleRequestCancel('button')}>
                            <Ban size={14} />
                            <span>Cancel Download</span>
                        </button>
                    </div>
                )}
            </div>

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

// frontend/src/components/Files/DownloadManager.tsx
import React, { useState, useEffect } from 'react';
import { Loader2, CheckCircle2, AlertTriangle, X } from 'lucide-react';
// Import the new API function and the status type
import { dismissDownloadAPI, type DownloadStatus } from '../../api/api';

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

    // This effect now only controls the visual "fading out" animation for auto-dismissal.
    // The actual removal is handled by the parent via WebSocket.
    useEffect(() => {
        let timer: NodeJS.Timeout;
        if (downloadStatus === 'completed' || downloadStatus === 'error') {
            // Start the closing animation after 4 seconds. The backend will send the
            // "remove" command after 30 seconds, which will remove the item from the DOM.
            timer = setTimeout(() => {
                setIsClosing(true);
            }, 4000);
        }
        return () => clearTimeout(timer);
    }, [downloadStatus]);

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

    const handleDismissClick = () => {
        setIsClosing(true); // Start closing animation immediately on click
        // After the animation, call the actual dismissal logic
        setTimeout(() => onDismiss(download_id), 300);
    };

    return (
        <div
            className={`download-item-toast ${downloadStatus} ${isClosing ? 'closing' : ''} transform transition-all duration-300 ease-in-out`}
            key={download_id}
            role="alert"
        >
            <div className="download-toast-header">
                <span className="download-toast-filename" title={filename}>{filename}</span>
                <span className="download-toast-status-icon">{getStatusIcon()}</span>
                <button onClick={handleDismissClick} className="dismiss-button">
                    <X size={16} />
                </button>
            </div>
            <div className="download-toast-body">
                {downloadStatus === 'error' ? (
                    <div className="download-toast-error-message" title={error_message || 'Unbekannter Fehler'}>
                        {error_message || 'Ein unbekannter Fehler ist aufgetreten.'}
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
        </div>
    );
};


interface DownloadManagerProps {
    activeDownloads: Map<string, DownloadStatus>;
}

// The DownloadManager is now a "dumb" component. It just renders the list
// it's given and calls a function when an item is dismissed.
const DownloadManager: React.FC<DownloadManagerProps> = ({ activeDownloads }) => {

    const handleDismiss = (downloadId: string) => {
        // This function now triggers the API call to remove the download "forever".
        // The component will re-render and the item will disappear when the parent
        // component receives the "remove" message via WebSocket and updates the prop.
        dismissDownloadAPI(downloadId).catch(err => {
            // Optional: Show an error toast if the dismissal fails
            console.error("Dismissal failed:", err);
        });
    };

    if (activeDownloads.size === 0) {
        return null;
    }

    // Convert map to array for rendering
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

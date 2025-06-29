// frontend/src/components/Files/DownloadManager.tsx
import React, { useState, useEffect } from 'react';
import { Loader2, CheckCircle2, AlertTriangle, X } from 'lucide-react';
import type { DownloadStatus } from '../../api/api'; // Import from the central api file

interface DownloadManagerProps {
    activeDownloads: Map<string, DownloadStatus>;
}

const DownloadItem: React.FC<{ status: DownloadStatus, onDismiss: (id: string) => void }> = ({ status, onDismiss }) => {
    const {
        download_id,
        filename,
        status: downloadStatus,
        progress,
        error_message,
    } = status;

    // --- ADDED: Auto-dismissal for completed/error states ---
    useEffect(() => {
        if (downloadStatus === 'completed' || downloadStatus === 'error') {
            const timer = setTimeout(() => {
                onDismiss(download_id);
            }, 5000); // Remove after 5 seconds

            return () => clearTimeout(timer);
        }
    }, [downloadStatus, download_id, onDismiss]);


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

    return (
        <div 
            className={`download-item-toast ${downloadStatus} transform transition-all duration-300 ease-in-out`} 
            key={download_id}
            role="alert"
        >
            <div className="download-toast-header">
                <span className="download-toast-filename" title={filename}>{filename}</span>
                <span className="download-toast-status-icon">{getStatusIcon()}</span>
                <button onClick={() => onDismiss(download_id)} className="dismiss-button">
                    <X size={16} />
                </button>
            </div>
            <div className="download-toast-body">
                {downloadStatus === 'error' ? (
                    <div className="download-toast-error-message" title={error_message || 'Unknown error'}>
                        {error_message || 'An unknown error occurred.'}
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
                        <span className="progress-text">{progress.toFixed(1)}%</span>
                    </>
                )}
            </div>
        </div>
    );
};


const DownloadManager: React.FC<DownloadManagerProps> = ({ activeDownloads }) => {
    // --- ADDED: Local state to handle dismissals without affecting the source map directly ---
    const [visibleDownloads, setVisibleDownloads] = useState<Map<string, DownloadStatus>>(new Map());

    useEffect(() => {
        // Sync with the prop, but don't remove items that are already fading out
        setVisibleDownloads(prevVisible => {
            const newVisible = new Map(prevVisible);
            // Add/update downloads from props
            activeDownloads.forEach((status, id) => {
                newVisible.set(id, status);
            });
            // The removal is handled by the dismiss callback
            return newVisible;
        });
    }, [activeDownloads]);

    const handleDismiss = (downloadId: string) => {
        setVisibleDownloads(prev => {
            const newMap = new Map(prev);
            newMap.delete(downloadId);
            return newMap;
        });
    };

    if (visibleDownloads.size === 0) {
        return null;
    }

    const downloadArray = Array.from(visibleDownloads.values());

    return (
        <div className="download-manager-container">
            {downloadArray.map(status => (
                <DownloadItem 
                    key={status.download_id} 
                    status={status} 
                    onDismiss={handleDismiss} 
                />
            ))}
            Hallo
        </div>
    );
};

export default DownloadManager;

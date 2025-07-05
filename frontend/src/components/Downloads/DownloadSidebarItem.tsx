// frontend/src/components/Downloads/DownloadSidebarItem.tsx
import React, { useState } from 'react';
import { Loader2, CheckCircle2, AlertTriangle, X, Ban } from 'lucide-react';
import { cancelDownloadAPI, type DownloadStatus } from '../../api/api';
import ConfirmModal from '../Layout/ConfirmModal';

interface DownloadSidebarItemProps {
    status: DownloadStatus;
    onDismiss: (downloadId: string) => void;
}

const DownloadSidebarItem: React.FC<DownloadSidebarItemProps> = ({ status, onDismiss }) => {
    const { download_id, filename, status: downloadStatus, progress, error_message } = status;

    const [isConfirmOpen, setIsConfirmOpen] = useState(false);

    // Prüft, ob der Download aktiv läuft und somit abgebrochen werden kann.
    const isCancellable = downloadStatus === 'pending' || downloadStatus === 'downloading';

    const getStatusIcon = () => {
        switch (downloadStatus) {
            case 'downloading':
                return <Loader2 size={18} className="animate-spin" />;
            case 'completed':
                return <CheckCircle2 size={18} className="icon-success" />;
            case 'cancelled':
                return <Ban size={18} className="icon-cancelled" />;
            case 'error':
                return <AlertTriangle size={18} className="icon-error" />;
            default:
                return <Loader2 size={18} className="animate-spin icon-pending" />;
        }
    };

    const handleRequestCancel = () => {
        setIsConfirmOpen(true);
    };

    const handleConfirmCancel = async () => {
        await cancelDownloadAPI(download_id);
        setIsConfirmOpen(false);
    };

    // NEU: Der intelligente Handler für den X-Button
    const handleActionClick = () => {
        if (isCancellable) {
            // Wenn der Download läuft, den Abbruch-Dialog öffnen.
            handleRequestCancel();
        } else {
            // Wenn der Download fertig/fehlgeschlagen/abgebrochen ist, das Item entfernen.
            onDismiss(download_id);
        }
    };

    return (
        <>
            <div className={`download-sidebar-item ${downloadStatus}`} role="alert">
                <div className="download-item-header">
                    <span className="download-item-status-icon">{getStatusIcon()}</span>
                    <span className="download-item-filename" title={filename}>
                        {filename}
                    </span>
                </div>
                
                <div className="download-item-body">
                    {downloadStatus === 'error' || downloadStatus === 'cancelled' ? (
                        <div
                            className="download-item-error-message"
                            title={error_message || 'Download was cancelled'}
                        >
                            {error_message || 'The download was cancelled by the user.'}
                        </div>
                    ) : (
                        <div className="progress-display">
                            <div className="progress-bar-container">
                                <div
                                    className={`progress-bar ${downloadStatus}`}
                                    style={{ width: `${progress}%` }}
                                />
                            </div>
                            <span className="progress-text">{progress?.toFixed(1) || '0.0'}%</span>
                        </div>
                    )}
                    {/* ENTFERNT: Der explizite Cancel-Button ist nicht mehr nötig. */}
                </div>

                <div className="download-item-actions">
                    <button
                        // NEU: Ruft den intelligenten Handler auf.
                        onClick={handleActionClick}
                        className="button-icon dismiss-button"
                        // NEU: Der Tooltip passt sich der Aktion an.
                        aria-label={isCancellable ? 'Cancel download' : 'Dismiss notification'}
                        title={isCancellable ? 'Cancel download' : 'Dismiss notification'}
                    >
                        <X size={16} />
                    </button>
                </div>
            </div>

            <ConfirmModal
                isOpen={isConfirmOpen}
                title="Cancel Download?"
                message={`Are you sure you want to cancel the download for "${filename}"?`}
                onConfirm={handleConfirmCancel}
                onCancel={() => setIsConfirmOpen(false)}
                confirmText="Yes, Cancel"
                isDanger={true}
            />
        </>
    );
};

export default DownloadSidebarItem;

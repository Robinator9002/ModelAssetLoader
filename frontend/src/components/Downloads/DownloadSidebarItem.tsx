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

    const handleManualDismiss = () => {
        onDismiss(download_id);
    };

    const handleRequestCancel = () => {
        setIsConfirmOpen(true);
    };

    const handleConfirmCancel = async () => {
        await cancelDownloadAPI(download_id);
        setIsConfirmOpen(false);
    };

    const isCancellable = downloadStatus === 'pending' || downloadStatus === 'downloading';

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
                        // NEU: Eigener Container für die Progress-Bar und den Text
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
                    {/* NEU: Expliziter Cancel-Button, der nur bei Bedarf erscheint */}
                    {isCancellable && (
                         <div className="download-item-cancel-action">
                             <button
                                 className="button button-danger button-small"
                                 onClick={handleRequestCancel}
                             >
                                 <Ban size={14} />
                                 <span>Cancel</span>
                             </button>
                         </div>
                    )}
                </div>

                {/* NEU: Der Schließen-Button ist jetzt in seinem eigenen Layout-Bereich */}
                <div className="download-item-actions">
                    <button
                        onClick={handleManualDismiss}
                        className="button-icon dismiss-button"
                        aria-label={'Dismiss notification'}
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

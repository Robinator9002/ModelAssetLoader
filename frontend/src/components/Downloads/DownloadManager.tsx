// frontend/src/components/Files/DownloadManager.tsx

import React, { useState, useEffect } from 'react';
import { Loader2, CheckCircle2, AlertTriangle, X, Ban } from 'lucide-react';
import { cancelDownloadAPI, type DownloadStatus } from '../../api/api';
import ConfirmModal from '../Layout/ConfirmModal';

interface DownloadItemProps {
    status: DownloadStatus;
    onDismiss: (downloadId: string) => void;
}

const DownloadItem: React.FC<DownloadItemProps> = ({ status, onDismiss }) => {
    const { download_id, filename, status: downloadStatus, progress, error_message } = status;

    const [isClosing, setIsClosing] = useState(false);
    const [isConfirmOpen, setIsConfirmOpen] = useState(false);

    // ====================================================================
    // ===== ZENTRALER EFFEKT FÜR DAS ENTFERNEN (DER GATEKEEPER) ======
    // ====================================================================
    // Dieser useEffect-Hook ist der Einzige, der die onDismiss-Funktion
    // aufrufen darf. Er wird nur aktiv, wenn `isClosing` true wird.
    useEffect(() => {
        if (isClosing) {
            // Warte 300ms, damit die CSS-Ausblende-Animation fertig wird.
            const dismissalTimer = setTimeout(() => {
                onDismiss(download_id);
            }, 300);

            // Cleanup-Funktion: Falls die Komponente aus einem anderen Grund
            // verschwindet, wird der Timer sicher gelöscht.
            return () => clearTimeout(dismissalTimer);
        }
    }, [isClosing, download_id, onDismiss]);

    // ====================================================================
    // ===== EFFEKT FÜR DAS AUTOMATISCHE SCHLIESSEN (DER TRIGGER) =====
    // ====================================================================
    // Dieser Effekt startet nur noch den Prozess, er führt ihn nicht aus.
    useEffect(() => {
        let autoDismissTimer: NodeJS.Timeout | undefined;

        if (
            downloadStatus === 'completed' ||
            downloadStatus === 'error' ||
            downloadStatus === 'cancelled'
        ) {
            autoDismissTimer = setTimeout(() => {
                setIsClosing(true); // Triggert den obigen "Gatekeeper"-Effekt
            }, 4000); // 4 Sekunden Wartezeit
        }

        // Löscht den Timer, wenn sich der Status ändert, bevor die 4s um sind.
        return () => clearTimeout(autoDismissTimer);
    }, [downloadStatus]);

    // --- Unveränderte Logik ---

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
            default:
                return <Loader2 size={18} className="animate-spin text-gray-400" />;
        }
    };

    // VEREINFACHT: Diese Funktion muss nur noch die Animation triggern.
    const handleManualDismiss = () => {
        setIsClosing(true); // Triggert den "Gatekeeper"-Effekt
    };

    const handleRequestCancel = () => {
        setIsConfirmOpen(true);
    };

    const handleConfirmCancel = async () => {
        await cancelDownloadAPI(download_id);
        // Nach dem Cancel-API-Call wird das Backend eine 'cancelled'-Status-Update senden.
        // Der auto-dismiss useEffect wird dies auffangen und den Toast nach 4s schließen.
    };

    const isCancellable = downloadStatus === 'pending' || downloadStatus === 'downloading';

    return (
        <>
            <div
                className={`download-item-toast ${downloadStatus} ${isClosing ? 'closing' : ''}`}
                role="alert"
            >
                <div className="download-toast-header">
                    <span className="download-toast-filename" title={filename}>
                        {filename}
                    </span>
                    <span className="download-toast-status-icon">{getStatusIcon()}</span>
                    <button
                        onClick={isCancellable ? handleRequestCancel : handleManualDismiss}
                        className="dismiss-button"
                        aria-label={isCancellable ? 'Request cancellation' : 'Dismiss notification'}
                    >
                        <X size={16} />
                    </button>
                </div>
                <div className="download-toast-body">
                    {downloadStatus === 'error' || downloadStatus === 'cancelled' ? (
                        <div
                            className="download-toast-error-message"
                            title={error_message || 'Download was cancelled'}
                        >
                            {error_message || 'The download was cancelled by the user.'}
                        </div>
                    ) : (
                        <>
                            <div className="progress-bar-container">
                                <div
                                    className={`progress-bar ${downloadStatus}`}
                                    style={{ width: `${progress}%` }}
                                />
                            </div>
                            <span className="progress-text">{progress?.toFixed(1) || '0.0'}%</span>
                        </>
                    )}
                </div>
                {isCancellable && (
                    <div className="download-toast-actions">
                        <button
                            className="button button-danger button-small"
                            onClick={handleRequestCancel}
                        >
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
                isDanger={true}
            />
        </>
    );
};

interface DownloadManagerProps {
    activeDownloads: Map<string, DownloadStatus>;
    onDismiss: (downloadId: string) => void;
}

// Dieser Teil bleibt unverändert
const DownloadManager: React.FC<DownloadManagerProps> = ({ activeDownloads, onDismiss }) => {
    if (activeDownloads.size === 0) {
        return null;
    }
    const downloadArray = Array.from(activeDownloads.values());
    return (
        <div className="download-manager-container">
            {downloadArray.map((status) => (
                <DownloadItem key={status.download_id} status={status} onDismiss={onDismiss} />
            ))}
        </div>
    );
};

export default DownloadManager;

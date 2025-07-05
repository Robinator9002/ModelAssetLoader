// frontend/src/components/Downloads/DownloadSidebar.tsx
import React from 'react';
import { X } from 'lucide-react';
import { type DownloadStatus } from '../../api/api';
import DownloadSidebarItem from './DownloadSidebarItem';

interface DownloadSidebarProps {
    isOpen: boolean;
    onClose: () => void;
    activeDownloads: Map<string, DownloadStatus>;
    onDismiss: (downloadId: string) => void;
}

const DownloadSidebar: React.FC<DownloadSidebarProps> = ({
    isOpen,
    onClose,
    activeDownloads,
    onDismiss,
}) => {
    const downloadArray = Array.from(activeDownloads.values());

    // Bestimme, ob es überhaupt Downloads gibt, die angezeigt werden können.
    const hasDownloads = downloadArray.length > 0;

    return (
        // Fügt die 'open'-Klasse hinzu, wenn die Sidebar sichtbar sein soll.
        <div className={`download-sidebar ${isOpen ? 'open' : ''}`}>
            <div className="download-sidebar-header">
                <h3>Active Downloads</h3>
                <button
                    onClick={onClose}
                    className="button-icon close-button"
                    aria-label="Close Downloads Sidebar"
                >
                    <X size={20} />
                </button>
            </div>
            <div className="download-sidebar-list">
                {hasDownloads ? (
                    downloadArray.map((status) => (
                        <DownloadSidebarItem
                            key={status.download_id}
                            status={status}
                            onDismiss={onDismiss}
                        />
                    ))
                ) : (
                    <div className="no-downloads-message">
                        <p>No active downloads.</p>
                    </div>
                )}
            </div>
        </div>
    );
};

export default DownloadSidebar;

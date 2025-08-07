// frontend/src/components/FileManager/FileItem.tsx
import React from 'react';
import { Folder, FileText, Trash2 } from 'lucide-react';
import { type LocalFileItem } from '~/api';

interface FileItemProps {
    item: LocalFileItem;
    onNavigate: (item: LocalFileItem) => void;
    onDelete: (item: LocalFileItem) => void;
}

// Helper to format file size
const formatBytes = (bytes: number | null, decimals = 2): string => {
    if (bytes === null || bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
};

const FileItem: React.FC<FileItemProps> = ({ item, onNavigate, onDelete }) => {
    // --- FIX: Changed item.type to item.item_type to match the API type definition ---
    const Icon = item.item_type === 'directory' ? Folder : FileText;

    const handleDeleteClick = (e: React.MouseEvent) => {
        e.stopPropagation(); // Prevent navigation when clicking delete
        onDelete(item);
    };

    const handleNavigateClick = () => {
        onNavigate(item);
    };

    return (
        <div className="file-item-card" onClick={handleNavigateClick} title={item.name}>
            <div className="file-item-icon-wrapper">
                {/* --- FIX: Changed item.type to item.item_type --- */}
                <Icon size={48} className={`file-item-icon type-${item.item_type}`} />
            </div>
            <div className="file-item-details">
                <p className="file-item-name">{item.name}</p>
                <p className="file-item-meta">
                    {/* --- FIX: Changed item.type to item.item_type --- */}
                    {item.item_type === 'file' ? formatBytes(item.size) : 'Directory'}
                </p>
            </div>
            <div className="file-item-actions">
                <button
                    className="button-icon delete-button"
                    title="Delete"
                    onClick={handleDeleteClick}
                >
                    <Trash2 size={16} />
                </button>
            </div>
        </div>
    );
};

export default FileItem;

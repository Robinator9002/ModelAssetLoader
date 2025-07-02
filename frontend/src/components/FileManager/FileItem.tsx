// frontend/src/components/FileManager/FileItem.tsx
import React from 'react';
import { Folder, FileText, Trash2 } from 'lucide-react';
import { type LocalFileItem } from '../../api/api';

interface FileItemProps {
    item: LocalFileItem;
    onNavigate: (item: LocalFileItem) => void;
    onDelete: (item: LocalFileItem) => void;
}

// Helper to format file size
const formatBytes = (bytes: number, decimals = 2): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
};

const FileItem: React.FC<FileItemProps> = ({ item, onNavigate, onDelete }) => {
    const Icon = item.type === 'directory' ? Folder : FileText;

    const handleDeleteClick = (e: React.MouseEvent) => {
        e.stopPropagation(); // Prevent navigation when clicking delete
        onDelete(item);
    };
    
    const handleNavigateClick = () => {
        onNavigate(item);
    }

    return (
        <div className="file-item-card" onClick={handleNavigateClick} title={item.name}>
            <div className="file-item-icon-wrapper">
                <Icon size={48} className={`file-item-icon type-${item.type}`} />
            </div>
            <div className="file-item-details">
                <p className="file-item-name">{item.name}</p>
                <p className="file-item-meta">
                    {item.type === 'file' && item.size !== null ? formatBytes(item.size) : 'Directory'}
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

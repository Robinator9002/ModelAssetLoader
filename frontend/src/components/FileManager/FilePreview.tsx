// frontend/src/components/FileManager/FilePreview.tsx
import React, { useState, useEffect } from 'react';
import { getFilePreviewAPI, type LocalFileItem } from '~/api';
import { X, Loader2, AlertTriangle } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

interface FilePreviewProps {
    item: LocalFileItem;
    onClose: () => void;
}

const FilePreview: React.FC<FilePreviewProps> = ({ item, onClose }) => {
    const [content, setContent] = useState<string>('');
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchPreview = async () => {
            setIsLoading(true);
            setError(null);
            try {
                const response = await getFilePreviewAPI(item.path);
                if (response.success && response.content) {
                    setContent(response.content);
                } else {
                    throw new Error(response.error || 'Could not load file content.');
                }
            } catch (err: any) {
                setError(err.message || 'An unknown error occurred.');
            } finally {
                setIsLoading(false);
            }
        };

        fetchPreview();
    }, [item.path]);

    const renderContent = () => {
        if (isLoading) {
            return (
                <div className="preview-feedback">
                    <Loader2 className="animate-spin" />
                    <span>Loading preview...</span>
                </div>
            );
        }
        if (error) {
            return (
                <div className="preview-feedback error">
                    <AlertTriangle />
                    <span>{error}</span>
                </div>
            );
        }
        // Use ReactMarkdown for .md files, otherwise render as plain text
        if (item.name.toLowerCase().endsWith('.md')) {
            return (
                <div className="markdown-content">
                    <ReactMarkdown>{content}</ReactMarkdown>
                </div>
            );
        }
        return <pre className="plaintext-content">{content}</pre>;
    };

    return (
        <div className="modal-overlay file-preview-overlay active">
            <div
                className="modal-content file-preview-content"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="modal-header">
                    <h3>Preview: {item.name}</h3>
                    <button onClick={onClose} className="button-icon close-button">
                        <X size={20} />
                    </button>
                </div>
                <div className="modal-body file-preview-body">{renderContent()}</div>
            </div>
        </div>
    );
};

export default FilePreview;

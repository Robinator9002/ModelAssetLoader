// frontend/src/components/Layout/FolderSelector.tsx
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { scanHostDirectoriesAPI, type HostDirectoryItem } from '../../api/api';
import { Folder, FolderOpen, RefreshCw, X, Check, HardDrive, AlertTriangle, ChevronRight, ChevronDown, Loader2 } from 'lucide-react';

const logger = {
    info: (...args: any[]) => console.log("[FolderSelector]", ...args),
    error: (...args: any[]) => console.error("[FolderSelector]", ...args),
};

const truncatePath = (path: string, maxLength: number = 60): string => {
    if (path.length <= maxLength) return path;
    const separator = path.includes('/') ? '/' : '\\';
    const parts = path.split(separator);
    if (parts.length <= 4) return path;
    const start = parts.slice(0, 2).join(separator);
    const end = parts.slice(-2).join(separator);
    const truncatedPath = `${start}${separator}...${separator}${end}`;
    return truncatedPath.length > maxLength ? path.substring(0, maxLength - 3) + '...' : truncatedPath;
};

interface MappedNode extends HostDirectoryItem {}

const FolderSelectorNode: React.FC<{ node: MappedNode; onNodeClick: (path: string) => void; selectedPath: string | null; expandedPaths: Set<string>; loadingPaths: Set<string>; level: number; }> = ({ node, onNodeClick, selectedPath, expandedPaths, loadingPaths, level }) => {
    const isSelected = selectedPath === node.path;
    const isLoading = loadingPaths.has(node.path);
    const isExpanded = expandedPaths.has(node.path);
    const Icon = level === 0 ? HardDrive : (isExpanded ? FolderOpen : Folder);
    const ExpandIcon = isLoading ? <Loader2 size={16} className="animate-spin" /> : (isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />);

    return (
        <li className={`folder-selector-item ${isSelected ? "selected" : ""}`} role="treeitem" aria-selected={isSelected}>
            <div className="item-content" onClick={() => onNodeClick(node.path)} title={node.path}>
                <span className="item-indent" style={{ width: `${level * 18}px` }} />
                <span className="item-expand-icon">{ExpandIcon}</span>
                <span className="item-icon"><Icon size={18} /></span>
                <span className="item-name">{node.name}</span>
            </div>
            {isExpanded && node.children && (
                <ul className="nested-list" role="group">
                    {node.children.map(child => <FolderSelectorNode key={child.path} node={child} onNodeClick={onNodeClick} selectedPath={selectedPath} expandedPaths={expandedPaths} loadingPaths={loadingPaths} level={level + 1} />)}
                </ul>
            )}
        </li>
    );
};


interface FolderSelectorProps {
    isOpen: boolean;
    onSelectFinalPath: (path: string) => void;
    onCancel: () => void;
}

const FolderSelector: React.FC<FolderSelectorProps> = ({ isOpen, onSelectFinalPath, onCancel }) => {
    const [treeData, setTreeData] = useState<MappedNode[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [loadingPaths, setLoadingPaths] = useState<Set<string>>(new Set());
    const [error, setError] = useState<string | null>(null);
    const [selectedPath, setSelectedPath] = useState<string | null>(null);
    const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set());

    const updateNodeChildren = (nodes: MappedNode[], path: string, children: MappedNode[]): MappedNode[] => {
        return nodes.map(node => {
            if (node.path === path) return { ...node, children };
            if (node.children) return { ...node, children: updateNodeChildren(node.children, path, children) };
            return node;
        });
    };
    
    const fetchDirectories = useCallback(async (path?: string) => {
        const isRoot = !path;
        if (isRoot) setIsLoading(true); else setLoadingPaths(prev => new Set(prev).add(path));
        setError(null);
        try {
            const response = await scanHostDirectoriesAPI(path);
            if (!response.success) throw new Error(response.error || 'Failed to fetch directories.');
            if (isRoot) {
                setTreeData(response.data || []);
            } else {
                setTreeData(prev => updateNodeChildren(prev, path, response.data || []));
            }
        } catch (err: any) {
            setError(err.message);
        } finally {
            if (isRoot) setIsLoading(false); else setLoadingPaths(prev => { const n = new Set(prev); n.delete(path); return n; });
        }
    }, []);

    useEffect(() => {
        if (isOpen) {
            setTreeData([]);
            setSelectedPath(null);
            setExpandedPaths(new Set());
            fetchDirectories();
        }
    }, [isOpen, fetchDirectories]);

    const handleNodeClick = useCallback(async (path: string) => {
        setSelectedPath(path);
        if (expandedPaths.has(path)) {
            setExpandedPaths(prev => { const n = new Set(prev); n.delete(path); return n; });
        } else {
            setExpandedPaths(prev => new Set(prev).add(path));
            // Check if children need to be fetched
            const findNode = (nodes: MappedNode[]): MappedNode | undefined => {
                for (const node of nodes) {
                    if (node.path === path) return node;
                    if (node.children) {
                        const found = findNode(node.children);
                        if(found) return found;
                    }
                }
            }
            const node = findNode(treeData);
            if (node && node.children === null) { // Children are unknown, fetch them
                await fetchDirectories(path);
            }
        }
    }, [expandedPaths, fetchDirectories, treeData]);

    if (!isOpen) return null;
    
    return (
        <div className="modal-overlay folder-selector-overlay active">
            <div className="modal-content folder-selector-content">
                <div className="folder-selector-header">
                    <h3>Select Base Folder</h3>
                    <button onClick={onCancel} className="close-button"><X size={20} /></button>
                </div>
                <div className="folder-selector-body">
                    <div className="folder-selector-path-bar">
                        <span className="current-path-display" title={selectedPath || 'No folder selected'}>Selected: {selectedPath ? truncatePath(selectedPath) : 'None'}</span>
                        <button onClick={() => fetchDirectories()} disabled={isLoading} className="path-button refresh-button"><RefreshCw size={16}/></button>
                    </div>
                    <div className="folder-selector-tree-container">
                        {isLoading ? <div className="loading-indicator full-width-loader"><Loader2 size={24} className="animate-spin" /><p>Scanning drives...</p></div> :
                         error ? <p className="error-message folder-selector-error"><AlertTriangle size={16}/>{error}</p> :
                         <ul className="folder-tree-root">
                            {treeData.map(node => <FolderSelectorNode key={node.path} node={node} onNodeClick={handleNodeClick} selectedPath={selectedPath} expandedPaths={expandedPaths} loadingPaths={loadingPaths} level={0} />)}
                         </ul>
                        }
                    </div>
                </div>
                <div className="folder-selector-actions">
                    <button onClick={onCancel} className="button modal-button cancel-button">Cancel</button>
                    <button onClick={() => selectedPath && onSelectFinalPath(selectedPath)} disabled={!selectedPath} className="button modal-button confirm-button"><Check size={18}/> Select Folder</button>
                </div>
            </div>
        </div>
    );
};

export default FolderSelector;

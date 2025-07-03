// frontend/src/components/Layout/FolderSelector.tsx
import React, { useState, useEffect, useCallback, useMemo } from "react";
import { scanHostDirectoriesAPI, type HostDirectoryItem } from "../../api/api";
import {
    Folder,
    FolderOpen,
    RefreshCw,
    X,
    Check,
    HardDrive,
    AlertTriangle,
    ChevronRight,
    ChevronDown,
    Loader2,
    ArrowRight,
} from "lucide-react";

const logger = {
    info: (...args: any[]) => {
        if (process.env.NODE_ENV === "development")
            console.log("[FolderSelector]", ...args);
    },
    error: (...args: any[]) => console.error("[FolderSelector]", ...args),
    warn: (...args: any[]) => console.warn("[FolderSelector]", ...args),
};

interface MappedNode {
    name: string;
    path: string;
    type: "file" | "directory";
    children: Array<{ path: string; name: string; type: string }> | null;
}

interface FolderSelectorNodeProps {
    node: MappedNode;
    onNodeClick: (path: string) => void;
    selectedPath: string | null;
    expandedPaths: Set<string>;
    loadingPaths: Set<string>;
    level?: number;
    treeDataMap: Map<string, MappedNode>;
}

const FolderSelectorNode: React.FC<FolderSelectorNodeProps> = ({
    node,
    onNodeClick,
    selectedPath,
    expandedPaths,
    loadingPaths,
    treeDataMap,
    level = 0,
}) => {
    const isSelected = selectedPath === node.path;
    const isLoadingChildren = loadingPaths.has(node.path);
    const canExpand = node.type === "directory";

    const currentNodeFromMap = treeDataMap.get(node.path) || node;
    const isExpanded = expandedPaths.has(node.path);
    const hasDisplayableChildren =
        Array.isArray(currentNodeFromMap.children) &&
        currentNodeFromMap.children.length > 0;

    const handleItemClick = (e: React.MouseEvent) => {
        e.stopPropagation();
        onNodeClick(node.path);
    };

    const Icon = useMemo(() => {
        if (!canExpand) return Folder; // Should ideally not happen if API is correct
        if (
            level === 0 &&
            (node.path.match(/^[A-Z]:\\$/i) || node.path === "/")
        )
            return HardDrive;
        return isExpanded ? FolderOpen : Folder;
    }, [canExpand, node.path, isExpanded, level]);

    const ExpandIcon = useMemo(() => {
        if (!canExpand)
            return <span className="item-expand-icon-placeholder" />;
        if (isLoadingChildren)
            return <Loader2 size={16} className="animate-spin" />;
        return isExpanded ? (
            <ChevronDown size={16} />
        ) : (
            <ChevronRight size={16} />
        );
    }, [canExpand, isLoadingChildren, isExpanded]);

    return (
        <li
            className={`folder-selector-item ${isSelected ? "selected" : ""}`}
            role="treeitem"
            aria-selected={isSelected}
            aria-expanded={canExpand ? isExpanded : undefined}
        >
            <div
                className="item-content"
                onClick={handleItemClick}
                onKeyPress={(e: React.KeyboardEvent<HTMLDivElement>) => {
                    if (e.key === "Enter" || e.key === " ") {
                        handleItemClick(e as any);
                    }
                }}
                tabIndex={0}
                title={node.path}
                style={{
                    paddingLeft: `calc(var(--spacing-unit) + ${level * 20}px)`,
                }}
            >
                <span className="item-expand-icon">{ExpandIcon}</span>
                <span className="item-icon">
                    <Icon size={18} />
                </span>
                <span className="item-name">{currentNodeFromMap.name}</span>
            </div>
            {isExpanded &&
                hasDisplayableChildren &&
                Array.isArray(currentNodeFromMap.children) && (
                    <ul className="nested-list" role="group">
                        {currentNodeFromMap.children.map(
                            (childPathInfo, index) => {
                                const childNode = treeDataMap.get(
                                    childPathInfo.path
                                );
                                if (!childNode) return null;
                                const uniqueKey = `${childNode.path}-${childNode.name}-${index}`;
                                return (
                                    <FolderSelectorNode
                                        key={uniqueKey}
                                        node={childNode}
                                        onNodeClick={onNodeClick}
                                        selectedPath={selectedPath}
                                        expandedPaths={expandedPaths}
                                        loadingPaths={loadingPaths}
                                        level={level + 1}
                                        treeDataMap={treeDataMap}
                                    />
                                );
                            }
                        )}
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

const FolderSelector: React.FC<FolderSelectorProps> = ({
    isOpen,
    onSelectFinalPath,
    onCancel,
}) => {
    const [treeDataMap, setTreeDataMap] = useState<Map<string, MappedNode>>(
        new Map()
    );
    const [rootPaths, setRootPaths] = useState<string[]>([]);
    const [isLoadingGlobal, setIsLoadingGlobal] = useState(false);
    const [loadingPaths, setLoadingPaths] = useState<Set<string>>(new Set());
    const [error, setError] = useState<string | null>(null);
    const [selectedPath, setSelectedPath] = useState<string | null>(null);
    const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set());
    const [pathInput, setPathInput] = useState<string>("");

    const API_SCAN_DEPTH = 1;

    const mapApiNodeToMappedNode = useCallback(
        (apiNode: HostDirectoryItem): MappedNode => ({
            name: apiNode.name,
            path: apiNode.path,
            type: apiNode.type,
            children: apiNode.children
                ? apiNode.children.map((c) => ({
                      path: c.path,
                      name: c.name,
                      type: c.type,
                  }))
                : null,
        }),
        []
    );

    const processAndStoreNodesRecursively = useCallback(
        (nodes: HostDirectoryItem[], map: Map<string, MappedNode>) => {
            nodes.forEach((apiNode) => {
                const mappedNode = mapApiNodeToMappedNode(apiNode);
                map.set(apiNode.path, mappedNode);
                // Check if children exist and is an array before recursing
                if (apiNode.children && Array.isArray(apiNode.children)) {
                    processAndStoreNodesRecursively(apiNode.children, map);
                }
            });
        },
        [mapApiNodeToMappedNode]
    );

    const fetchDirectoryStructure = useCallback(
        async (path?: string, isRootScan: boolean = false) => {
            const targetPath = path || "";
            if (isRootScan) setIsLoadingGlobal(true);
            else setLoadingPaths((prev) => new Set(prev).add(targetPath));
            setError(null);

            try {
                const response = await scanHostDirectoriesAPI(
                    targetPath || undefined,
                    API_SCAN_DEPTH
                );
                // Ensure response.data is a non-empty array before processing
                if (
                    response?.success &&
                    response.data &&
                    Array.isArray(response.data)
                ) {
                    setTreeDataMap((prevMap) => {
                        const newMap = new Map(prevMap);
                        if (response.data) {
                            if (isRootScan) {
                                processAndStoreNodesRecursively(
                                    response.data,
                                    newMap
                                );
                                setRootPaths(
                                    response.data.map((node) => node.path)
                                );
                            } else {
                                const parentNodeFromApi = response.data[0];
                                if (
                                    parentNodeFromApi &&
                                    parentNodeFromApi.path === targetPath
                                ) {
                                    const parentMappedNode =
                                        mapApiNodeToMappedNode(
                                            parentNodeFromApi
                                        );
                                    // Check if children exist before processing
                                    if (
                                        parentNodeFromApi.children &&
                                        Array.isArray(
                                            parentNodeFromApi.children
                                        )
                                    ) {
                                        processAndStoreNodesRecursively(
                                            parentNodeFromApi.children,
                                            newMap
                                        );
                                    }
                                    newMap.set(targetPath, parentMappedNode);
                                }
                            }
                        }
                        return newMap;
                    });
                } else {
                    setError(
                        response?.error || "Failed to load directory structure."
                    );
                    if (isRootScan) setRootPaths([]);
                }
            } catch (err: any) {
                logger.error(
                    `Error fetching structure for ${targetPath}:`,
                    err
                );
                setError(err.message || "A critical error occurred.");
            } finally {
                if (isRootScan) setIsLoadingGlobal(false);
                else
                    setLoadingPaths((prev) => {
                        const n = new Set(prev);
                        n.delete(targetPath);
                        return n;
                    });
            }
        },
        [processAndStoreNodesRecursively, mapApiNodeToMappedNode]
    );

    useEffect(() => {
        if (isOpen) {
            setTreeDataMap(new Map());
            setRootPaths([]);
            setSelectedPath(null);
            setExpandedPaths(new Set());
            setPathInput("");
            setError(null);
            fetchDirectoryStructure(undefined, true);
        }
    }, [isOpen, fetchDirectoryStructure]);

    const handleNodeInteraction = useCallback(
        async (path: string) => {
            setSelectedPath(path);
            setPathInput(path);
            setError(null);

            const node = treeDataMap.get(path);
            if (node?.type !== "directory") return;

            const isExpanded = expandedPaths.has(path);
            if (isExpanded) {
                setExpandedPaths((prev) => {
                    const n = new Set(prev);
                    n.delete(path);
                    return n;
                });
            } else {
                if (node.children === null) {
                    // Only fetch if children are unknown
                    await fetchDirectoryStructure(path, false);
                }
                setExpandedPaths((prev) => new Set(prev).add(path));
            }
        },
        [treeDataMap, expandedPaths, fetchDirectoryStructure]
    );

    const handleConfirmSelection = useCallback(() => {
        if (selectedPath) {
            const selectedNode = treeDataMap.get(selectedPath);
            if (selectedNode?.type === "directory") {
                onSelectFinalPath(selectedPath);
            } else {
                setError("Please select a valid folder.");
            }
        } else {
            setError("Please select a folder or enter a path.");
        }
    }, [selectedPath, treeDataMap, onSelectFinalPath]);

    const handleRefreshRoot = useCallback(() => {
        fetchDirectoryStructure(undefined, true);
    }, [fetchDirectoryStructure]);

    const handleGoToPathInput = useCallback(async () => {
        const trimmedPath = pathInput.trim();
        if (!trimmedPath) {
            setError("Please enter a path.");
            return;
        }
        await fetchDirectoryStructure(trimmedPath, false);
        setSelectedPath(trimmedPath);
        setExpandedPaths((prev) => new Set(prev).add(trimmedPath));
    }, [pathInput, fetchDirectoryStructure]);

    const treeRootNodes = rootPaths
        .map((path) => treeDataMap.get(path))
        .filter(Boolean) as MappedNode[];
    const isBusy = isLoadingGlobal || loadingPaths.size > 0;

    if (!isOpen) return null;

    return (
        <div
            className={`modal-overlay folder-selector-overlay ${
                isOpen ? "active" : ""
            }`}
        >
            <div className="modal-content folder-selector-content">
                <div className="modal-header">
                    <h3>Select Base Folder</h3>
                    <button
                        onClick={onCancel}
                        className="button-icon close-button"
                        aria-label="Close"
                        disabled={isBusy}
                    >
                        <X size={20} />
                    </button>
                </div>
                <div className="modal-body folder-selector-body">
                    <div className="folder-selector-controls">
                        <div className="path-input-group">
                            <input
                                type="text"
                                value={pathInput}
                                onChange={(e) => setPathInput(e.target.value)}
                                placeholder="Select a folder below or enter a path..."
                                className="path-input-manual"
                                onKeyDown={(
                                    e: React.KeyboardEvent<HTMLInputElement>
                                ) => e.key === "Enter" && handleGoToPathInput()}
                                disabled={isBusy}
                            />
                            <button
                                onClick={handleGoToPathInput}
                                className="button-icon go-button"
                                aria-label="Go to path"
                                disabled={!pathInput.trim() || isBusy}
                            >
                                <ArrowRight size={16} />
                            </button>
                        </div>
                        <button
                            onClick={handleRefreshRoot}
                            className="button-icon refresh-button"
                            aria-label="Refresh root directories"
                            disabled={isBusy}
                        >
                            <RefreshCw size={16} />
                        </button>
                    </div>

                    <div className="folder-selector-tree-container">
                        {isLoadingGlobal && (
                            <div className="feedback-container">
                                <Loader2 size={24} className="animate-spin" />
                                <p>Loading root directories...</p>
                            </div>
                        )}
                        {error && (
                            <div className="feedback-container">
                                <AlertTriangle
                                    size={24}
                                    className="icon-error"
                                />
                                <p>{error}</p>
                            </div>
                        )}
                        {!isLoadingGlobal &&
                            !error &&
                            treeRootNodes.length === 0 && (
                                <div className="feedback-container">
                                    <p>
                                        No directories found. Check backend logs
                                        and permissions.
                                    </p>
                                </div>
                            )}
                        {!isLoadingGlobal &&
                            !error &&
                            treeRootNodes.length > 0 && (
                                <ul className="folder-tree-root" role="tree">
                                    {treeRootNodes.map((node, index) => (
                                        <FolderSelectorNode
                                            key={`${node.path}-${index}`}
                                            node={node}
                                            onNodeClick={handleNodeInteraction}
                                            selectedPath={selectedPath}
                                            expandedPaths={expandedPaths}
                                            loadingPaths={loadingPaths}
                                            level={0}
                                            treeDataMap={treeDataMap}
                                        />
                                    ))}
                                </ul>
                            )}
                    </div>
                </div>
                <div className="modal-actions">
                    <button
                        className="button"
                        onClick={onCancel}
                        disabled={isBusy}
                    >
                        Cancel
                    </button>
                    <button
                        className="button button-primary"
                        onClick={handleConfirmSelection}
                        disabled={
                            !selectedPath ||
                            isBusy ||
                            treeDataMap.get(selectedPath!)?.type !== "directory"
                        }
                    >
                        <Check size={18} /> Select Folder
                    </button>
                </div>
            </div>
        </div>
    );
};
export default FolderSelector;

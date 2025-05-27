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
    onNodeClick: (path: string, currentLevel: number) => Promise<void>;
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
        onNodeClick(node.path, level);
    };

    const Icon = useMemo(() => {
        if (!canExpand) return Folder;
        if (
            level === 0 &&
            (node.path.match(/^[A-Z]:\\$/i) || node.path === "/")
        )
            return HardDrive;
        return isExpanded ? FolderOpen : Folder;
    }, [canExpand, node.path, isExpanded, level]);

    const ExpandIcon = useMemo(() => {
        if (!canExpand)
            return <span style={{ width: "1.5em", display: "inline-block" }} />;
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
            style={{ paddingLeft: `${level * 20}px` }}
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
                                if (!childNode) {
                                    logger.warn(
                                        `[Node:${currentNodeFromMap.name}] Child node with path ${childPathInfo.path} not found in treeDataMap.`
                                    );
                                    return null;
                                }
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
    const [currentDisplayPath, setCurrentDisplayPath] = useState<string>("");
    const [selectedPath, setSelectedPath] = useState<string | null>(null);
    const [expandedPaths, _setExpandedPaths] = useState<Set<string>>(new Set());
    const [pathInput, setPathInput] = useState<string>("");

    const setExpandedPaths = useCallback(
        (
            updater: Set<string> | ((prevState: Set<string>) => Set<string>),
            _caller?: string
        ) => {
            _setExpandedPaths((prev) => {
                const newSet =
                    typeof updater === "function" ? updater(prev) : updater;
                return newSet;
            });
        },
        []
    );

    const API_SCAN_DEPTH_FOR_ROOTS = 1;
    const API_SCAN_DEPTH_FOR_EXPAND = 1;

    const mapApiNodeToMappedNode = useCallback(
        (apiNode: HostDirectoryItem): MappedNode => {
            let childrenRefs: Array<{
                path: string;
                name: string;
                type: string;
            }> | null;
            if (apiNode.children === null || apiNode.children === undefined) {
                childrenRefs = null;
            } else if (Array.isArray(apiNode.children)) {
                childrenRefs =
                    apiNode.children.length > 0
                        ? apiNode.children.map((c) => ({
                              path: c.path,
                              name: c.name,
                              type: c.type,
                          }))
                        : [];
            } else {
                logger.warn(
                    `[mapApiNodeToMappedNode] apiNode.children for ${apiNode.path} is invalid:`,
                    apiNode.children
                );
                childrenRefs = null;
            }
            return {
                name: apiNode.name,
                path: apiNode.path,
                type: apiNode.type,
                children: childrenRefs,
            };
        },
        []
    );

    const processAndStoreNodesRecursively = useCallback(
        (
            nodesFromApi: HostDirectoryItem[],
            mapToUpdate: Map<string, MappedNode>
        ) => {
            nodesFromApi.forEach((apiNode) => {
                const newMappedNode = mapApiNodeToMappedNode(apiNode);

                const existingNode = mapToUpdate.get(apiNode.path);
                if (
                    apiNode.path === "/" &&
                    newMappedNode.name !== "/" &&
                    existingNode &&
                    existingNode.name === "/"
                ) {
                    if (existingNode.children && !newMappedNode.children) {
                        logger.warn(
                            `[processAndStoreNodesRecursively] Symlink ${newMappedNode.name} (${apiNode.path}) would overwrite actual root with less info. Skipping.`
                        );
                        return;
                    }
                }

                if (
                    existingNode &&
                    !newMappedNode.children &&
                    existingNode.children
                ) {
                    logger.warn(
                        `[processAndStoreNodesRecursively] New node for ${apiNode.path} has no children, existing has. Preferring existing children.`
                    );
                    newMappedNode.children = existingNode.children;
                    if (apiNode.path === "/" && newMappedNode.name !== "/")
                        newMappedNode.name = existingNode.name; // Prefer original name for root
                }
                mapToUpdate.set(apiNode.path, newMappedNode);

                if (
                    apiNode.children &&
                    Array.isArray(apiNode.children) &&
                    apiNode.children.length > 0
                ) {
                    processAndStoreNodesRecursively(
                        apiNode.children,
                        mapToUpdate
                    );
                }
            });
        },
        [mapApiNodeToMappedNode]
    );

    const fetchDirectoryStructure = useCallback(
        async (
            path?: string,
            isRootScan: boolean = false
        ): Promise<boolean> => {
            const targetPath = path || "";
            const scanDepth = isRootScan
                ? API_SCAN_DEPTH_FOR_ROOTS
                : API_SCAN_DEPTH_FOR_EXPAND;
            if (
                isRootScan ||
                (process.env.NODE_ENV === "development" && path === "/run")
            ) {
                // Minimal info logging
                logger.info(
                    `Workspaceing structure for path: '${
                        targetPath || "[ROOTS]"
                    }', isRoot: ${isRootScan}, depth: ${scanDepth}`
                );
            }
            if (isRootScan) setIsLoadingGlobal(true);
            else setLoadingPaths((prev) => new Set(prev).add(targetPath));
            setError(null);
            let operationSuccessful = false;

            try {
                const response = await scanHostDirectoriesAPI(
                    targetPath || undefined,
                    scanDepth
                );
                if (response?.success) {
                    if (response.data) {
                        setTreeDataMap((prevMap) => {
                            const newMap = new Map(prevMap);
                            if (isRootScan) {
                                if (response.data && response.data.length > 0) {
                                    processAndStoreNodesRecursively(
                                        response.data,
                                        newMap
                                    );
                                    const newRootPathsList = response.data.map(
                                        (rootNode) => rootNode.path
                                    );
                                    setRootPaths(newRootPathsList);
                                    // Log final root node state after root scan
                                    if (
                                        process.env.NODE_ENV ===
                                            "development" &&
                                        newRootPathsList.length > 0 &&
                                        newMap.has(newRootPathsList[0])
                                    ) {
                                        const finalRoot = newMap.get(
                                            newRootPathsList[0]
                                        );
                                        console.log(
                                            `[FolderSelector:DEBUG] Root scan complete. Root node (${
                                                finalRoot?.path
                                            }) in map: Name: ${
                                                finalRoot?.name
                                            }, Children: ${JSON.stringify(
                                                finalRoot?.children
                                            )}`
                                        );
                                    }
                                } else {
                                    setRootPaths([]);
                                }
                            } else if (targetPath) {
                                const parentNodeFromApi = response.data?.[0];
                                if (
                                    parentNodeFromApi &&
                                    parentNodeFromApi.path === targetPath
                                ) {
                                    const parentMappedNode =
                                        mapApiNodeToMappedNode(
                                            parentNodeFromApi
                                        );
                                    if (
                                        parentMappedNode.path === "/" &&
                                        parentMappedNode.name !== "/"
                                    ) {
                                        parentMappedNode.name = "/";
                                    }

                                    // Process children first, carefully
                                    if (
                                        parentNodeFromApi.children &&
                                        parentNodeFromApi.children.length > 0
                                    ) {
                                        parentNodeFromApi.children.forEach(
                                            (childApiNode) => {
                                                const childMappedNode =
                                                    mapApiNodeToMappedNode(
                                                        childApiNode
                                                    );
                                                if (
                                                    childApiNode.path !==
                                                    targetPath
                                                ) {
                                                    newMap.set(
                                                        childApiNode.path,
                                                        childMappedNode
                                                    );
                                                } else if (
                                                    childApiNode.path === "/" &&
                                                    childMappedNode.name !== "/"
                                                ) {
                                                    const existingRootCheck =
                                                        newMap.get("/");
                                                    if (
                                                        existingRootCheck &&
                                                        existingRootCheck.name ===
                                                            "/"
                                                    ) {
                                                        if (
                                                            existingRootCheck.children &&
                                                            !childMappedNode.children
                                                        )
                                                            return; // Skip less informative symlink
                                                    }
                                                    newMap.set(
                                                        childApiNode.path,
                                                        childMappedNode
                                                    ); // Update if not worse
                                                } else {
                                                    newMap.set(
                                                        childApiNode.path,
                                                        childMappedNode
                                                    );
                                                }
                                            }
                                        );
                                    }
                                    newMap.set(targetPath, parentMappedNode); // Set parent last
                                    // if (process.env.NODE_ENV === 'development') {
                                    //    console.log(`[FolderSelector:DEBUG] Expanded ${targetPath}. Parent in map: Name: ${parentMappedNode.name}, Children: ${JSON.stringify(parentMappedNode.children)}`);
                                    // }
                                } else {
                                    const nodeToUpdate = newMap.get(targetPath);
                                    if (nodeToUpdate)
                                        newMap.set(targetPath, {
                                            ...nodeToUpdate,
                                            children: [],
                                        });
                                    logger.warn(
                                        `[setTreeDataMap EXPAND ${targetPath}] API response for ${targetPath} was not as expected.`
                                    );
                                }
                            }
                            return newMap;
                        });
                        if (isRootScan)
                            setCurrentDisplayPath("Wurzelverzeichnisse");
                        operationSuccessful = true;
                    } else {
                        if (targetPath && !isRootScan) {
                            setTreeDataMap((prevMap) => {
                                const newMap = new Map(prevMap);
                                const nodeToUpdate = newMap.get(targetPath);
                                if (nodeToUpdate)
                                    newMap.set(targetPath, {
                                        ...nodeToUpdate,
                                        children: [],
                                    });
                                else
                                    newMap.set(targetPath, {
                                        name:
                                            targetPath.split("/").pop() ||
                                            targetPath,
                                        path: targetPath,
                                        type: "directory",
                                        children: [],
                                    });
                                return newMap;
                            });
                            operationSuccessful = true;
                        } else if (isRootScan) {
                            setRootPaths([]);
                            setCurrentDisplayPath("Wurzelverzeichnisse");
                            operationSuccessful = true;
                        }
                    }
                } else {
                    setError(
                        response?.error ||
                            "Verzeichnisstruktur konnte nicht geladen werden."
                    );
                    if (isRootScan) setRootPaths([]);
                    else if (targetPath) {
                        setTreeDataMap((prevMap) => {
                            const newMap = new Map(prevMap);
                            const nodeToUpdate = newMap.get(targetPath);
                            if (nodeToUpdate)
                                newMap.set(targetPath, {
                                    ...nodeToUpdate,
                                    children: null,
                                });
                            return newMap;
                        });
                    }
                }
            } catch (err: any) {
                logger.error(
                    `Error in fetchDirectoryStructure for ${
                        targetPath || "[ROOTS]"
                    }:`,
                    err
                );
                setError(
                    err.message || "Ein schwerwiegender Fehler ist aufgetreten."
                );
                if (isRootScan) setRootPaths([]);
                else if (targetPath) {
                    setTreeDataMap((prevMap) => {
                        const newMap = new Map(prevMap);
                        const nodeToUpdate = newMap.get(targetPath);
                        if (nodeToUpdate)
                            newMap.set(targetPath, {
                                ...nodeToUpdate,
                                children: null,
                            });
                        return newMap;
                    });
                }
            } finally {
                if (isRootScan) setIsLoadingGlobal(false);
                else {
                    setLoadingPaths((prev) => {
                        const n = new Set(prev);
                        n.delete(targetPath);
                        return n;
                    });
                }
            }
            return operationSuccessful;
        },
        [processAndStoreNodesRecursively, mapApiNodeToMappedNode]
    );

    useEffect(() => {
        if (isOpen) {
            logger.info(
                "FolderSelector wird geöffnet. States zurücksetzen, Wurzeln laden."
            );
            setTreeDataMap(new Map());
            setRootPaths([]);
            setSelectedPath(null);
            setExpandedPaths(new Set(), "useEffect[isOpen]");
            setPathInput("");
            setCurrentDisplayPath("");
            setError(null);
            fetchDirectoryStructure(undefined, true);
        }
    }, [isOpen, fetchDirectoryStructure, setExpandedPaths]);

    const handleNodeInteraction = useCallback(
        async (path: string, level: number) => {
            setSelectedPath(path);
            setCurrentDisplayPath(path);
            setPathInput(path);
            setError(null);

            const nodeFromMap = treeDataMap.get(path);
            const isCurrentlyExpanded = expandedPaths.has(path);
            const childrenAreUnknown =
                !nodeFromMap || nodeFromMap.children === null;
            const isLoadingThisPath = loadingPaths.has(path);

            if (nodeFromMap && nodeFromMap.type !== "directory") {
                setExpandedPaths((prev) => {
                    if (prev.has(path)) {
                        const n = new Set(prev);
                        n.delete(path);
                        return n;
                    }
                    return prev;
                }, `file ${path}`);
                return;
            }

            if (isCurrentlyExpanded) {
                setExpandedPaths((prev) => {
                    const n = new Set(prev);
                    n.delete(path);
                    return n;
                }, `collapse ${path}`);
            } else {
                if (childrenAreUnknown && !isLoadingThisPath) {
                    // logger.info(`[InteractionAttempt: ${path}] Children unknown and not loading. Fetching...`);
                    await fetchDirectoryStructure(path, false);
                }
                setExpandedPaths((prev) => {
                    const n = new Set(prev);
                    n.add(path);
                    return n;
                }, `expand ${path}`);
            }
        },
        [
            treeDataMap,
            fetchDirectoryStructure,
            loadingPaths,
            setExpandedPaths,
            selectedPath,
            expandedPaths,
        ]
    );

    const handleConfirmSelection = useCallback(() => {
        if (selectedPath) {
            const selectedNode = treeDataMap.get(selectedPath);
            if (selectedNode && selectedNode.type === "directory") {
                onSelectFinalPath(selectedPath);
            } else {
                setError("Bitte wählen Sie einen gültigen Ordner aus.");
            }
        } else {
            setError(
                "Bitte wählen Sie einen Ordner aus oder geben Sie einen Pfad ein."
            );
        }
    }, [selectedPath, treeDataMap, onSelectFinalPath]);

    const handleRefreshRoot = useCallback(() => {
        logger.info("Refreshing root directories.");
        setTreeDataMap(new Map());
        setRootPaths([]);
        setSelectedPath(null);
        setExpandedPaths(new Set(), "handleRefreshRoot");
        setError(null);
        setPathInput("");
        setCurrentDisplayPath("");
        fetchDirectoryStructure(undefined, true);
    }, [fetchDirectoryStructure, setExpandedPaths]);

    const handleGoToPathInput = useCallback(async () => {
        const trimmedPath = pathInput.trim();
        if (trimmedPath) {
            await handleNodeInteraction(trimmedPath, -1);
        } else {
            setError("Bitte geben Sie einen Pfad ein.");
        }
    }, [pathInput, handleNodeInteraction]);

    const treeRootNodes = rootPaths
        .map((path) => treeDataMap.get(path))
        .filter(Boolean) as MappedNode[];

    if (!isOpen) return null;

    return (
        <div
            className={`modal-overlay folder-selector-overlay ${
                isOpen ? "active" : ""
            }`}
        >
            <div className="modal-content folder-selector-content">
                <div className="folder-selector-header">
                    <h3>Basisordner auswählen</h3>
                    <button
                        onClick={onCancel}
                        className="close-button"
                        title="Schließen"
                        disabled={isLoadingGlobal || loadingPaths.size > 0}
                    >
                        <X size={20} />
                    </button>
                </div>
                <div className="folder-selector-body">
                    <div className="folder-selector-path-bar">
                        <span
                            className="current-path-display"
                            title={currentDisplayPath}
                        >
                            Ausgewählt: {currentDisplayPath || "Keine Auswahl"}
                        </span>
                        <button
                            onClick={handleRefreshRoot}
                            disabled={isLoadingGlobal || loadingPaths.size > 0}
                            title="Wurzelverzeichnisse neu laden"
                            className="path-button refresh-button"
                        >
                            <RefreshCw size={16} />
                        </button>
                    </div>
                    <div className="folder-selector-input-bar">
                        <input
                            type="text"
                            value={pathInput}
                            onChange={(e) => setPathInput(e.target.value)}
                            placeholder="Pfad manuell eingeben oder auswählen..."
                            className="path-input-manual"
                            onKeyDown={(
                                e: React.KeyboardEvent<HTMLInputElement>
                            ) => {
                                if (e.key === "Enter") {
                                    handleGoToPathInput();
                                }
                            }}
                            disabled={isLoadingGlobal || loadingPaths.size > 0}
                        />
                        <button
                            onClick={handleGoToPathInput}
                            className="path-button go-button"
                            title="Gehe zu Pfad"
                            disabled={
                                !pathInput.trim() ||
                                isLoadingGlobal ||
                                loadingPaths.size > 0
                            }
                        >
                            Go
                        </button>
                    </div>
                    <div className="folder-selector-tree-container">
                        {isLoadingGlobal && (
                            <div className="loading-indicator full-width-loader">
                                <Loader2 size={24} className="animate-spin" />
                                <p>
                                    Lade Wurzelverzeichnisse (Tiefe{" "}
                                    {API_SCAN_DEPTH_FOR_ROOTS})...
                                </p>
                            </div>
                        )}
                        {error && (
                            <p className="error-message folder-selector-error">
                                {" "}
                                <AlertTriangle size={16} /> {error}{" "}
                            </p>
                        )}
                        {!isLoadingGlobal &&
                            !error &&
                            treeRootNodes.length === 0 && (
                                <p className="no-results-message">
                                    {" "}
                                    Keine Verzeichnisse gefunden. Prüfen Sie
                                    Backend-Logs und Berechtigungen.{" "}
                                </p>
                            )}
                        {!isLoadingGlobal &&
                            !error &&
                            treeRootNodes.length > 0 && (
                                <ul className="folder-tree-root" role="tree">
                                    {treeRootNodes.map((node, index) => (
                                        <FolderSelectorNode
                                            key={`${node.path}-${node.name}-${index}`}
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
                <div className="folder-selector-actions">
                    <button
                        className="button modal-button cancel-button"
                        onClick={onCancel}
                        disabled={isLoadingGlobal || loadingPaths.size > 0}
                    >
                        {" "}
                        Abbrechen{" "}
                    </button>
                    <button
                        className="button modal-button confirm-button"
                        onClick={handleConfirmSelection}
                        disabled={
                            !selectedPath ||
                            isLoadingGlobal ||
                            loadingPaths.size > 0 ||
                            !!(
                                selectedPath &&
                                treeDataMap.get(selectedPath)?.type !==
                                    "directory"
                            )
                        }
                    >
                        <Check size={18} /> Ordner Auswählen
                    </button>
                </div>
            </div>
        </div>
    );
};
export default FolderSelector;

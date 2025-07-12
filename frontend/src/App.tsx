// frontend/src/App.tsx
import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import './App.css';
import Navbar, { type MalTabKey } from './components/Layout/Navbar';
import ThemeSwitcher from './components/Theme/ThemeSwitcher';
import ModelSearchPage from './components/ModelLoader/ModelSearchPage';
import ModelDetailsPage from './components/ModelLoader/ModelDetailsPage';
import ConfigurationsPage from './components/Files/ConfigurationsPage';
import DownloadModal from './components/Downloads/DownloadModal';
import DownloadSidebar from './components/Downloads/DownloadSidebar';
import FileManagerPage from './components/FileManager/FileManagerPage';
import UiManagementPage from './components/Environments/UiManagementPage';
import appIcon from '/icon.png';

import {
    // All available API functions are imported for use within the App component.
    listAvailableUisAPI,
    getUiStatusesAPI,
    installUiAPI,
    runUiAPI,
    stopUiAPI,
    deleteUiAPI,
    repairUiAPI,
    finalizeAdoptionAPI,
    getCurrentConfigurationAPI,
    configurePathsAPI,
    connectToDownloadTracker,
    // All necessary type definitions are imported to ensure type safety.
    type ColorThemeType,
    type ModelListItem,
    type ModelDetails,
    type ModelFile,
    type DownloadStatus,
    type AvailableUiItem,
    type ManagedUiStatus,
    type UiNameType,
    type ConfigurationMode,
    type UiProfileType,
    type UiInstallRequest,
} from './api/api';
import dismissDownloadAPI from './api/api'

/**
 * A simple, namespaced logger for monitoring component lifecycle and state changes
 * during development.
 */
const logger = {
    info: (...args: any[]) => console.log('[App]', ...args),
    error: (...args: any[]) => console.error('[App]', ...args),
};

/**
 * Defines the comprehensive shape of the application's core path and UI configuration state.
 */
export interface AppPathConfig {
    basePath: string | null;
    uiProfile: UiProfileType | null;
    customPaths: Record<string, string>;
    configMode: ConfigurationMode;
    automaticModeUi: UiNameType | null;
}

/**
 * Represents the summarized status of all background tasks for UI feedback.
 */
export type DownloadSummaryStatus = 'idle' | 'downloading' | 'error' | 'completed';

/**
 * The default, unconfigured state for the application's path settings.
 */
const defaultPathConfig: AppPathConfig = {
    basePath: null,
    uiProfile: null,
    customPaths: {},
    configMode: 'automatic',
    automaticModeUi: null,
};

/**
 * The root component of the M.A.L. application. It manages all global state,
 * API interactions, and renders the main layout and active views.
 */
function App() {
    // --- Core Application State ---
    const [pathConfig, setPathConfig] = useState<AppPathConfig>(defaultPathConfig);
    const [theme, setTheme] = useState<ColorThemeType>('dark');
    const [activeTab, setActiveTab] = useState<MalTabKey>('environments');
    const [isConfigLoading, setIsConfigLoading] = useState<boolean>(true);

    // --- View & Modal States ---
    const [selectedModel, setSelectedModel] = useState<ModelListItem | null>(null);
    const [isDownloadModalOpen, setIsDownloadModalOpen] = useState(false);
    const [modelForDownload, setModelForDownload] = useState<ModelDetails | null>(null);
    const [specificFileForDownload, setSpecificFileForDownload] = useState<ModelFile | null>(null);

    // --- Download & Task Management State ---
    const [activeDownloads, setActiveDownloads] = useState<Map<string, DownloadStatus>>(new Map());
    const [isDownloadsSidebarOpen, setDownloadsSidebarOpen] = useState(false);
    const [tasksToAutoConfigure, setTasksToAutoConfigure] = useState<Set<string>>(new Set());
    const ws = useRef<WebSocket | null>(null);

    // --- UI Environment Management State ---
    const [availableUis, setAvailableUis] = useState<AvailableUiItem[]>([]);
    const [uiStatuses, setUiStatuses] = useState<ManagedUiStatus[]>([]);

    /**
     * Fetches all UI-related data from the backend, including both the list of
     * installable UIs and the statuses of already managed ones.
     */
    const fetchUiData = useCallback(async () => {
        try {
            const [uis, statuses] = await Promise.all([listAvailableUisAPI(), getUiStatusesAPI()]);
            setAvailableUis(uis);
            setUiStatuses(statuses.items);
        } catch (error: any) {
            logger.error('Failed to fetch UI environment data:', error);
        }
    }, []);

    /**
     * Automatically updates the application's configuration to use a newly installed
     * or adopted UI. This is triggered when a task completes that was marked for
     * this behavior.
     * @param {UiNameType} uiName The name of the UI to set as the active configuration.
     */
    const handleAutoConfigureUi = useCallback(
        async (uiName: UiNameType) => {
            const uiInfo = availableUis.find((ui) => ui.ui_name === uiName);
            if (!uiInfo) {
                logger.error(`Cannot auto-configure: UI info for '${uiName}' not found.`);
                return;
            }

            logger.info(`Auto-configuring settings for newly active UI: ${uiName}`);
            try {
                const response = await configurePathsAPI({
                    config_mode: 'automatic',
                    automatic_mode_ui: uiName,
                    profile: uiInfo.default_profile_name,
                });

                if (response.success && response.current_config) {
                    const newConfig = response.current_config;
                    handlePathConfigurationUpdate(
                        {
                            basePath: newConfig.base_path,
                            uiProfile: newConfig.profile,
                            customPaths: newConfig.custom_model_type_paths || {},
                            configMode: newConfig.config_mode || 'automatic',
                            automaticModeUi: newConfig.automatic_mode_ui || null,
                        },
                        newConfig.color_theme || theme,
                    );
                } else {
                    throw new Error(response.error || 'Failed to auto-configure paths.');
                }
            } catch (error: any) {
                logger.error('Failed during auto-configuration:', error);
            }
        },
        [availableUis, theme],
    );

    /**
     * Establishes and manages the WebSocket connection for receiving real-time
     * updates on background tasks like downloads, installations, and running processes.
     */
    useEffect(() => {
        if (ws.current) return;

        logger.info('Setting up WebSocket for download and task tracking...');
        const handleWsMessage = (data: any) => {
            switch (data.type) {
                case 'initial_state':
                    setActiveDownloads(
                        new Map(
                            (data.downloads || []).map((s: DownloadStatus) => [s.download_id, s]),
                        ),
                    );
                    break;
                case 'update':
                    const status: DownloadStatus = data.data;
                    if (status?.download_id) {
                        setActiveDownloads((prev) => new Map(prev).set(status.download_id, status));

                        if (status.status === 'completed' && status.repo_id?.includes('UI')) {
                            logger.info(
                                `UI task for '${status.filename}' completed. Refreshing UI statuses.`,
                            );
                            fetchUiData();

                            if (tasksToAutoConfigure.has(status.download_id)) {
                                handleAutoConfigureUi(status.filename as UiNameType);
                                setTasksToAutoConfigure((prev) => {
                                    const newSet = new Set(prev);
                                    newSet.delete(status.download_id);
                                    return newSet;
                                });
                            }
                        }
                    }
                    break;
                case 'remove':
                    if (data.download_id) {
                        setActiveDownloads((prev) => {
                            const newMap = new Map(prev);
                            newMap.delete(data.download_id);
                            return newMap;
                        });
                    }
                    break;
            }
        };
        ws.current = connectToDownloadTracker(handleWsMessage);

        return () => {
            if (ws.current?.readyState === WebSocket.OPEN) ws.current.close();
            ws.current = null;
        };
    }, [fetchUiData, tasksToAutoConfigure, handleAutoConfigureUi]);

    /**
     * Handles the initial loading of the application's configuration from the backend
     * when the component first mounts.
     */
    const loadInitialConfig = useCallback(async () => {
        setIsConfigLoading(true);
        try {
            const config = await getCurrentConfigurationAPI();
            setPathConfig({
                basePath: config.base_path,
                uiProfile: config.profile,
                customPaths: config.custom_model_type_paths || {},
                configMode: config.config_mode || 'automatic',
                automaticModeUi: config.automatic_mode_ui || null,
            });
            setTheme(config.color_theme || 'dark');
            await fetchUiData();
        } catch (error: any) {
            logger.error('Failed to load initial config:', error);
        } finally {
            setIsConfigLoading(false);
        }
    }, [fetchUiData]);

    // Effect to run the initial configuration load once on mount.
    useEffect(() => {
        loadInitialConfig();
    }, [loadInitialConfig]);

    /**
     * Toggles the application's color theme and persists the change to the backend.
     */
    const handleThemeToggleAndSave = useCallback(async () => {
        const newTheme = theme === 'light' ? 'dark' : 'light';
        setTheme(newTheme);
        try {
            await configurePathsAPI({ color_theme: newTheme });
        } catch (error: any) {
            logger.error('Failed to save theme to backend:', error);
        }
    }, [theme]);

    // Effect to apply the current theme class to the document body.
    useEffect(() => {
        document.body.className = theme === 'light' ? 'light-theme' : '';
    }, [theme]);

    /**
     * A callback function passed to the configuration page to update the app's
     * global state when settings are saved.
     * @param {AppPathConfig} updatedConfig The newly saved path configuration.
     * @param {ColorThemeType} [updatedTheme] The newly saved color theme.
     */
    const handlePathConfigurationUpdate = useCallback(
        (updatedConfig: AppPathConfig, updatedTheme?: ColorThemeType) => {
            setPathConfig(updatedConfig);
            if (updatedTheme) setTheme(updatedTheme);
            fetchUiData();
        },
        [fetchUiData],
    );

    // --- UI Environment Action Handlers ---

    /**
     * Initiates the installation of a UI environment.
     * @param {UiInstallRequest} request The installation request details.
     */
    const handleInstallUi = useCallback(async (request: UiInstallRequest) => {
        try {
            const response = await installUiAPI(request);
            if (response.success && response.set_as_active_on_completion) {
                setTasksToAutoConfigure((prev) => new Set(prev).add(response.task_id));
            }
            setDownloadsSidebarOpen(true);
        } catch (error: any) {
            logger.error(`Failed to start installation for ${request.ui_name}:`, error);
        }
    }, []);

    /**
     * Starts a managed UI environment as a background process.
     * @param {UiNameType} uiName The name of the UI to run.
     */
    const handleRunUi = useCallback(async (uiName: UiNameType) => {
        try {
            await runUiAPI(uiName);
            setDownloadsSidebarOpen(true);
        } catch (error: any) {
            logger.error(`Failed to start UI ${uiName}:`, error);
        }
    }, []);

    /**
     * Stops a running UI environment process.
     * @param {string} taskId The task ID of the running process.
     */
    const handleStopUi = useCallback(async (taskId: string) => {
        try {
            await stopUiAPI(taskId);
        } catch (error: any) {
            logger.error(`Failed to stop UI task ${taskId}:`, error);
        }
    }, []);

    /**
     * Permanently deletes a managed UI environment's files and removes it from the registry.
     * @param {UiNameType} uiName The name of the UI to delete.
     */
    const handleDeleteUi = useCallback(
        async (uiName: UiNameType) => {
            try {
                await deleteUiAPI(uiName);
                fetchUiData();
            } catch (error: any) {
                logger.error(`Failed to delete UI ${uiName}:`, error);
            }
        },
        [fetchUiData],
    );

    /**
     * Initiates a background task to repair an existing UI installation.
     * @param {UiNameType} uiName The name of the UI to repair.
     * @param {string} path The absolute path to the UI installation.
     * @param {string[]} issuesToFix A list of issue codes to be addressed.
     */
    const handleRepairUi = useCallback(
        async (uiName: UiNameType, path: string, issuesToFix: string[]) => {
            try {
                const response = await repairUiAPI({
                    ui_name: uiName,
                    path,
                    issues_to_fix: issuesToFix,
                });
                // By convention, repaired UIs are set to be active.
                if (response.success) {
                    setTasksToAutoConfigure((prev) => new Set(prev).add(response.task_id));
                }
                setDownloadsSidebarOpen(true);
            } catch (error: any) {
                logger.error(`Failed to start repair for ${uiName}:`, error);
            }
        },
        [],
    );

    /**
     * Finalizes the adoption of a healthy or user-accepted UI installation by
     * registering it with the application.
     * @param {UiNameType} uiName The name of the UI to adopt.
     * @param {string} path The absolute path to the UI installation.
     */
    const handleFinalizeAdoption = useCallback(
        async (uiName: UiNameType, path: string) => {
            try {
                const response = await finalizeAdoptionAPI({ ui_name: uiName, path });
                if (response.success) {
                    logger.info(`Successfully adopted ${uiName}. Refreshing data.`);
                    fetchUiData();
                } else {
                    throw new Error('Backend failed to finalize adoption.');
                }
            } catch (error: any) {
                logger.error(`Failed to finalize adoption for ${uiName}:`, error);
            }
        },
        [fetchUiData],
    );

    /**
     * Checks if a specific UI is currently involved in a background task.
     * @param {UiNameType} uiName The name of the UI to check.
     * @returns {boolean} True if the UI is busy, false otherwise.
     */
    const isUiBusy = useCallback(
        (uiName: UiNameType): boolean => {
            return Array.from(activeDownloads.values()).some(
                (d) =>
                    d.filename === uiName && (d.status === 'pending' || d.status === 'downloading'),
            );
        },
        [activeDownloads],
    );

    // --- Download & Modal Action Handlers ---

    /**
     * Toggles the visibility of the downloads sidebar.
     */
    const handleToggleDownloadsSidebar = useCallback(() => setDownloadsSidebarOpen((p) => !p), []);
    const handleCloseDownloadsSidebar = useCallback(() => setDownloadsSidebarOpen(false), []);

    /**
     * Callback executed after download tasks have been successfully initiated.
     * Closes the download modal and opens the sidebar to show progress.
     */
    const handleDownloadsStarted = useCallback(() => {
        setIsDownloadModalOpen(false);
        setModelForDownload(null);
        setSpecificFileForDownload(null);
        setDownloadsSidebarOpen(true);
    }, []);

    /**
     * Opens the download modal to configure and start downloading files for a model.
     * @param {ModelDetails} modelDetails The full details of the model.
     * @param {ModelFile} [specificFile] An optional specific file to pre-select.
     */
    const openDownloadModal = useCallback(
        (modelDetails: ModelDetails, specificFile?: ModelFile) => {
            setModelForDownload(modelDetails);
            setSpecificFileForDownload(specificFile || null);
            setIsDownloadModalOpen(true);
        },
        [],
    );

    /**
     * Closes the download modal and resets its state.
     */
    const closeDownloadModal = useCallback(() => {
        setIsDownloadModalOpen(false);
        setModelForDownload(null);
        setSpecificFileForDownload(null);
    }, []);

    /**
     * Dismisses a completed or failed task from the sidebar view.
     * @param {string} downloadId The ID of the task to dismiss.
     */
    const handleDismissDownload = useCallback((downloadId: string) => {
        setActiveDownloads((prev) => {
            const newMap = new Map(prev);
            newMap.delete(downloadId);
            return newMap;
        });
        dismissDownloadAPI(downloadId).catch((error: any) =>
            logger.error(`Failed to dismiss download ${downloadId}:`, error),
        );
    }, []);

    // --- Memoized Derived State ---

    /**
     * Calculates a single summary status for all active downloads, used to style the
     * downloads icon in the navbar.
     */
    const downloadSummaryStatus = useMemo((): DownloadSummaryStatus => {
        const statuses = Array.from(activeDownloads.values());
        if (statuses.length === 0) return 'idle';
        if (statuses.some((s) => s.status === 'error')) return 'error';
        if (
            statuses.some(
                (s) =>
                    s.status === 'downloading' || s.status === 'pending' || s.status === 'running',
            )
        )
            return 'downloading';
        return 'completed';
    }, [activeDownloads]);

    /**
     * Combines the list of all available UIs with their current installation status.
     */
    const combinedManagedUis = useMemo(() => {
        const availableMap = new Map(availableUis.map((ui) => [ui.ui_name, ui]));
        return uiStatuses.map((status) => ({
            ...status,
            ...availableMap.get(status.ui_name),
        }));
    }, [availableUis, uiStatuses]);

    /**
     * Determines which UI is considered "active" for the quick-start button in the navbar,
     * based on the current configuration mode.
     */
    const activeUiForQuickStart = useMemo(() => {
        const targetUiName =
            pathConfig.configMode === 'automatic'
                ? pathConfig.automaticModeUi
                : pathConfig.uiProfile;
        if (!targetUiName || targetUiName === 'Custom') return null;
        return combinedManagedUis.find((s) => s.ui_name === targetUiName) || null;
    }, [pathConfig, combinedManagedUis]);

    /**
     * Handler for the quick-start button, which either starts or stops the active UI.
     */
    const handleQuickStart = useCallback(() => {
        if (!activeUiForQuickStart) return;
        if (activeUiForQuickStart.is_running && activeUiForQuickStart.running_task_id) {
            handleStopUi(activeUiForQuickStart.running_task_id);
        } else if (activeUiForQuickStart.is_installed) {
            handleRunUi(activeUiForQuickStart.ui_name);
        }
    }, [activeUiForQuickStart, handleRunUi, handleStopUi]);

    /**
     * Renders the content for the currently selected main tab.
     */
    const renderActiveTabContent = () => {
        if (isConfigLoading) {
            return <p className="loading-message">Loading configuration...</p>;
        }
        if (selectedModel) {
            return (
                <ModelDetailsPage
                    selectedModel={selectedModel}
                    onBack={() => setSelectedModel(null)}
                    openDownloadModal={openDownloadModal}
                />
            );
        }

        switch (activeTab) {
            case 'search':
                return (
                    <ModelSearchPage
                        onModelSelect={setSelectedModel}
                        openDownloadModal={openDownloadModal}
                        isConfigurationDone={!!pathConfig?.basePath}
                    />
                );
            case 'files':
                return <FileManagerPage />;
            case 'environments':
                return (
                    <UiManagementPage
                        availableUis={availableUis}
                        uiStatuses={uiStatuses}
                        onInstall={handleInstallUi}
                        onRun={handleRunUi}
                        onStop={handleStopUi}
                        onDelete={handleDeleteUi}
                        isBusy={isUiBusy}
                        onRepair={handleRepairUi}
                        onFinalizeAdoption={handleFinalizeAdoption}
                    />
                );
            case 'configuration':
                return (
                    <ConfigurationsPage
                        initialPathConfig={pathConfig}
                        onConfigurationSave={handlePathConfigurationUpdate}
                        currentGlobalTheme={theme}
                        managedUis={combinedManagedUis}
                    />
                );
            default:
                // Fallback to the search page if the tab is not recognized.
                return (
                    <ModelSearchPage
                        onModelSelect={setSelectedModel}
                        openDownloadModal={openDownloadModal}
                        isConfigurationDone={!!pathConfig?.basePath}
                    />
                );
        }
    };

    return (
        <div className={`app-wrapper ${isDownloadsSidebarOpen ? 'sidebar-open' : ''}`}>
            <DownloadSidebar
                isOpen={isDownloadsSidebarOpen}
                onClose={handleCloseDownloadsSidebar}
                activeDownloads={activeDownloads}
                onDismiss={handleDismissDownload}
            />
            <div className="app-content-pusher">
                <header className="app-header-placeholder">
                    <div
                        style={{
                            gap: '1rem',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                        }}
                    >
                        <img
                            src={appIcon}
                            style={{ width: '2rem', height: 'auto' }}
                            alt="M.A.L. Icon"
                        />
                        <h1>M.A.L.</h1>
                    </div>
                </header>
                <Navbar
                    activeTab={activeTab}
                    onTabChange={(tab) => {
                        setSelectedModel(null);
                        setActiveTab(tab);
                    }}
                    onToggleDownloads={handleToggleDownloadsSidebar}
                    downloadStatus={downloadSummaryStatus}
                    downloadCount={activeDownloads.size}
                    activeUiProfile={activeUiForQuickStart?.ui_name || null}
                    isUiInstalled={activeUiForQuickStart?.is_installed || false}
                    isUiRunning={activeUiForQuickStart?.is_running || false}
                    onQuickStart={handleQuickStart}
                />
                <main className="main-content-area">{renderActiveTabContent()}</main>
            </div>
            <div className="theme-switcher-container">
                <ThemeSwitcher currentTheme={theme} onToggleTheme={handleThemeToggleAndSave} />
            </div>
            <DownloadModal
                isOpen={isDownloadModalOpen}
                onClose={closeDownloadModal}
                modelDetails={modelForDownload}
                specificFileToDownload={specificFileForDownload}
                onDownloadsStarted={handleDownloadsStarted}
            />
        </div>
    );
}

export default App;

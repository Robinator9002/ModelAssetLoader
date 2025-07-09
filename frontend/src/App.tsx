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

import {
    // All API functions are imported
    listAvailableUisAPI,
    getUiStatusesAPI,
    installUiAPI,
    runUiAPI,
    stopUiAPI,
    deleteUiAPI,
    getCurrentConfigurationAPI,
    configurePathsAPI,
    connectToDownloadTracker,
    dismissDownloadAPI,
    // All type definitions are imported
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
} from './api/api';
import appIcon from '/icon.png';

const logger = {
    info: (...args: any[]) => console.log('[App]', ...args),
    error: (...args: any[]) => console.error('[App]', ...args),
};

// The comprehensive shape of the application's configuration state.
export interface AppPathConfig {
    basePath: string | null;
    uiProfile: UiProfileType | null;
    customPaths: Record<string, string>;
    configMode: ConfigurationMode;
    automaticModeUi: UiNameType | null;
}

export type DownloadSummaryStatus = 'idle' | 'downloading' | 'error' | 'completed';

const defaultPathConfig: AppPathConfig = {
    basePath: null,
    uiProfile: null,
    customPaths: {},
    configMode: 'automatic',
    automaticModeUi: null,
};

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
    const ws = useRef<WebSocket | null>(null);

    // --- UI Environment Management State ---
    const [availableUis, setAvailableUis] = useState<AvailableUiItem[]>([]);
    const [uiStatuses, setUiStatuses] = useState<ManagedUiStatus[]>([]);

    const fetchUiData = useCallback(async () => {
        try {
            const [uis, statuses] = await Promise.all([listAvailableUisAPI(), getUiStatusesAPI()]);
            setAvailableUis(uis);
            setUiStatuses(statuses.items);
        } catch (error) {
            logger.error('Failed to fetch UI environment data:', error);
        }
    }, []);

    // Effect to establish and manage the WebSocket connection for real-time updates.
    useEffect(() => {
        if (ws.current) return;

        logger.info('Setting up WebSocket for download and task tracking...');
        const handleWsMessage = (data: any) => {
            switch (data.type) {
                case 'initial_state': {
                    const initialMap = new Map<string, DownloadStatus>(
                        (data.downloads || []).map((s: DownloadStatus) => [s.download_id, s]),
                    );
                    setActiveDownloads(initialMap);
                    break;
                }
                case 'update': {
                    const status: DownloadStatus = data.data;
                    if (status?.download_id) {
                        setActiveDownloads((prev) => new Map(prev).set(status.download_id, status));

                        if (status.status === 'completed' && status.repo_id === 'UI Installation') {
                            logger.info(
                                `Installation for '${status.filename}' completed. Refreshing UI statuses.`,
                            );
                            fetchUiData();
                        }
                    }
                    break;
                }
                case 'remove': {
                    if (data.download_id) {
                        setActiveDownloads((prev) => {
                            const newMap = new Map(prev);
                            newMap.delete(data.download_id);
                            return newMap;
                        });
                    }
                    break;
                }
            }
        };
        ws.current = connectToDownloadTracker(handleWsMessage);

        return () => {
            if (ws.current?.readyState === WebSocket.OPEN) ws.current.close();
            ws.current = null;
        };
    }, [fetchUiData]);

    // --- Handlers for various UI actions ---
    const handleToggleDownloadsSidebar = useCallback(() => setDownloadsSidebarOpen((p) => !p), []);
    const handleCloseDownloadsSidebar = useCallback(() => setDownloadsSidebarOpen(false), []);

    const handleDownloadsStarted = useCallback(() => {
        setIsDownloadModalOpen(false);
        setModelForDownload(null);
        setSpecificFileForDownload(null);
        setDownloadsSidebarOpen(true);
    }, []);

    const openDownloadModal = useCallback(
        (modelDetails: ModelDetails, specificFile?: ModelFile) => {
            setModelForDownload(modelDetails);
            setSpecificFileForDownload(specificFile || null);
            setIsDownloadModalOpen(true);
        },
        [],
    );

    const closeDownloadModal = useCallback(() => {
        setIsDownloadModalOpen(false);
        setModelForDownload(null);
        setSpecificFileForDownload(null);
    }, []);

    const handleInstallUi = useCallback(async (uiName: UiNameType) => {
        try {
            await installUiAPI(uiName);
            setDownloadsSidebarOpen(true);
        } catch (error) {
            logger.error(`Failed to start installation for ${uiName}:`, error);
        }
    }, []);

    const handleRunUi = useCallback(async (uiName: UiNameType) => {
        try {
            await runUiAPI(uiName);
            setDownloadsSidebarOpen(true);
        } catch (error) {
            logger.error(`Failed to start UI ${uiName}:`, error);
        }
    }, []);

    const handleStopUi = useCallback(async (taskId: string) => {
        try {
            await stopUiAPI(taskId);
        } catch (error) {
            logger.error(`Failed to stop UI task ${taskId}:`, error);
        }
    }, []);

    const handleDeleteUi = useCallback(
        async (uiName: UiNameType) => {
            try {
                await deleteUiAPI(uiName);
                fetchUiData();
            } catch (error) {
                logger.error(`Failed to delete UI ${uiName}:`, error);
            }
        },
        [fetchUiData],
    );

    const isUiBusy = useCallback(
        (uiName: UiNameType): boolean => {
            return Array.from(activeDownloads.values()).some(
                (d) =>
                    d.filename === uiName && (d.status === 'pending' || d.status === 'downloading'),
            );
        },
        [activeDownloads],
    );

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
        } catch (error) {
            logger.error('Failed to load initial config:', error);
        } finally {
            setIsConfigLoading(false);
        }
    }, [fetchUiData]);

    useEffect(() => {
        loadInitialConfig();
    }, [loadInitialConfig]);

    useEffect(() => {
        document.body.className = theme === 'light' ? 'light-theme' : '';
    }, [theme]);

    const handleThemeToggleAndSave = useCallback(async () => {
        const newTheme = theme === 'light' ? 'dark' : 'light';
        setTheme(newTheme);
        try {
            await configurePathsAPI({ color_theme: newTheme });
        } catch (error) {
            logger.error('Failed to save theme to backend:', error);
        }
    }, [theme]);

    const handlePathConfigurationUpdate = useCallback(
        (updatedConfig: AppPathConfig, updatedTheme?: ColorThemeType) => {
            setPathConfig(updatedConfig);
            if (updatedTheme) setTheme(updatedTheme);
            fetchUiData();
        },
        [fetchUiData],
    );

    const handleDismissDownload = useCallback((downloadId: string) => {
        setActiveDownloads((prev) => {
            const newMap = new Map(prev);
            newMap.delete(downloadId);
            return newMap;
        });
        dismissDownloadAPI(downloadId).catch((error) =>
            logger.error(`Failed to dismiss download ${downloadId}:`, error),
        );
    }, []);

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

    // Combine available UI info with their live status for easier prop drilling.
    const combinedManagedUis = useMemo(() => {
        const availableMap = new Map(availableUis.map((ui) => [ui.ui_name, ui]));
        return uiStatuses.map((status) => ({
            ...status,
            ...availableMap.get(status.ui_name),
        }));
    }, [availableUis, uiStatuses]);

    // Determine the active UI for the "Quick Start" button based on config mode.
    const activeUiForQuickStart = useMemo(() => {
        const targetUiName =
            pathConfig.configMode === 'automatic'
                ? pathConfig.automaticModeUi
                : pathConfig.uiProfile;

        if (!targetUiName || targetUiName === 'Custom') return null;
        return combinedManagedUis.find((s) => s.ui_name === targetUiName) || null;
    }, [pathConfig, combinedManagedUis]);

    const handleQuickStart = useCallback(() => {
        if (!activeUiForQuickStart) return;
        if (activeUiForQuickStart.is_running && activeUiForQuickStart.running_task_id) {
            handleStopUi(activeUiForQuickStart.running_task_id);
        } else if (activeUiForQuickStart.is_installed) {
            handleRunUi(activeUiForQuickStart.ui_name);
        }
    }, [activeUiForQuickStart, handleRunUi, handleStopUi]);

    const renderActiveTabContent = () => {
        if (isConfigLoading) return <p className="loading-message">Loading configuration...</p>;
        if (selectedModel)
            return (
                <ModelDetailsPage
                    selectedModel={selectedModel}
                    onBack={() => setSelectedModel(null)}
                    openDownloadModal={openDownloadModal}
                />
            );

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

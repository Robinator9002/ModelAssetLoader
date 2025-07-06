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
    // API functions for UI management
    listAvailableUisAPI,
    getUiStatusesAPI,
    installUiAPI,
    runUiAPI,
    stopUiAPI,
    deleteUiAPI,
    // Existing API functions
    getCurrentConfigurationAPI,
    configurePathsAPI,
    connectToDownloadTracker,
    dismissDownloadAPI,
    // Type definitions
    type PathConfigurationRequest,
    type ColorThemeType,
    type MalFullConfiguration,
    type ModelListItem,
    type ModelDetails,
    type ModelFile,
    type DownloadStatus,
    type AvailableUiItem,
    type ManagedUiStatus,
    type UiNameType,
} from './api/api';
import appIcon from '/icon.png';

const logger = {
    info: (...args: any[]) => console.log('[App]', ...args),
    error: (...args: any[]) => console.error('[App]', ...args),
};

export interface AppPathConfig {
    basePath: string | null;
    uiProfile: MalFullConfiguration['profile'];
    customPaths: MalFullConfiguration['custom_model_type_paths'];
}

export type DownloadSummaryStatus = 'idle' | 'downloading' | 'error' | 'completed';

function App() {
    // --- Core Application State ---
    const [pathConfig, setPathConfig] = useState<AppPathConfig | null>(null);
    const [theme, setTheme] = useState<ColorThemeType>('dark');
    const [activeTab, setActiveTab] = useState<MalTabKey>('search');
    const [isConfigLoading, setIsConfigLoading] = useState<boolean>(true);

    // --- View & Modal States ---
    const [selectedModel, setSelectedModel] = useState<ModelListItem | null>(null);
    const [isDownloadModalOpen, setIsDownloadModalOpen] = useState<boolean>(false);
    const [modelForDownload, setModelForDownload] = useState<ModelDetails | null>(null);
    const [specificFileForDownload, setSpecificFileForDownload] = useState<ModelFile | null>(null);

    // --- Download Management State ---
    const [activeDownloads, setActiveDownloads] = useState<Map<string, DownloadStatus>>(new Map());
    const [isDownloadsSidebarOpen, setDownloadsSidebarOpen] = useState(false);
    const ws = useRef<WebSocket | null>(null);

    // --- UI Environment Management State ---
    const [availableUis, setAvailableUis] = useState<AvailableUiItem[]>([]);
    const [uiStatuses, setUiStatuses] = useState<ManagedUiStatus[]>([]);

    // Effect to establish and manage the WebSocket connection for real-time download updates.
    useEffect(() => {
        // WebSocket connection logic remains the same...
        if (!ws.current) {
            logger.info('Setting up WebSocket for download tracking...');
            const handleWsMessage = (data: any) => {
                switch (data.type) {
                    case 'initial_state': {
                        const initialMap = new Map<string, DownloadStatus>();
                        if (data.downloads && Array.isArray(data.downloads)) {
                            data.downloads.forEach((status: DownloadStatus) => {
                                initialMap.set(status.download_id, status);
                            });
                        }
                        setActiveDownloads(initialMap);
                        break;
                    }
                    case 'update': {
                        const status: DownloadStatus = data.data;
                        if (status && status.download_id) {
                            setActiveDownloads((prev) =>
                                new Map(prev).set(status.download_id, status),
                            );
                        }
                        break;
                    }
                    case 'remove': {
                        const { download_id } = data;
                        if (download_id) {
                            setActiveDownloads((prev) => {
                                const newMap = new Map(prev);
                                newMap.delete(download_id);
                                return newMap;
                            });
                        }
                        break;
                    }
                }
            };
            const socket = connectToDownloadTracker(handleWsMessage);
            ws.current = socket;
        }
        return () => {
            if (ws.current && ws.current.readyState === WebSocket.OPEN) {
                ws.current.close();
            }
            ws.current = null;
        };
    }, []);

    // --- Handlers for Download Sidebar ---
    const handleToggleDownloadsSidebar = useCallback(() => {
        setDownloadsSidebarOpen((prev) => !prev);
    }, []);

    const handleCloseDownloadsSidebar = useCallback(() => {
        setDownloadsSidebarOpen(false);
    }, []);

    const handleDownloadsStarted = useCallback(() => {
        setIsDownloadModalOpen(false);
        setModelForDownload(null);
        setSpecificFileForDownload(null);
        setDownloadsSidebarOpen(true);
    }, []);

    // --- Handlers for Download Modal ---
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

    // --- UI Management Data Fetching & Handlers ---
    const fetchUiData = useCallback(async () => {
        try {
            const [uis, statuses] = await Promise.all([listAvailableUisAPI(), getUiStatusesAPI()]);
            setAvailableUis(uis);
            setUiStatuses(statuses.items);
        } catch (error) {
            logger.error('Failed to fetch UI environment data:', error);
        }
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
            for (const download of activeDownloads.values()) {
                if (
                    download.filename === uiName &&
                    (download.status === 'pending' || download.status === 'downloading')
                ) {
                    return true;
                }
            }
            return false;
        },
        [activeDownloads],
    );

    // --- QUICK START LOGIC ---
    const activeUiProfileForStart = useMemo(() => {
        const profileName = pathConfig?.uiProfile;
        if (!profileName || profileName === 'Custom') return null;
        return uiStatuses.find((s) => s.ui_name === profileName) || null;
    }, [pathConfig, uiStatuses]);

    const handleQuickStart = useCallback(() => {
        if (!activeUiProfileForStart) return;

        if (activeUiProfileForStart.is_running && activeUiProfileForStart.running_task_id) {
            handleStopUi(activeUiProfileForStart.running_task_id);
        } else {
            handleRunUi(activeUiProfileForStart.ui_name);
        }
    }, [activeUiProfileForStart, handleRunUi, handleStopUi]);

    // --- General App Logic & Handlers ---
    const loadInitialConfig = useCallback(async () => {
        setIsConfigLoading(true);
        try {
            const config = await getCurrentConfigurationAPI();
            const newPathConfig = {
                basePath: config.base_path,
                uiProfile: config.profile,
                customPaths: config.custom_model_type_paths || {},
            };
            setPathConfig(newPathConfig);
            setTheme(config.color_theme || 'dark');
            await fetchUiData();
        } catch (error) {
            logger.error('Failed to load initial config from backend:', error);
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
            const configRequest: PathConfigurationRequest = {
                ...pathConfig,
                color_theme: newTheme,
                base_path: pathConfig?.basePath || null,
            };
            await configurePathsAPI(configRequest);
        } catch (error) {
            logger.error('Failed to save theme to backend:', error);
        }
    }, [theme, pathConfig]);

    const handleModelSelect = useCallback((model: ModelListItem) => {
        setSelectedModel(model);
    }, []);

    const handleBackToSearch = useCallback(() => {
        setSelectedModel(null);
    }, []);

    const handlePathConfigurationUpdate = useCallback(
        (updatedConfig: AppPathConfig, updatedTheme?: ColorThemeType) => {
            setPathConfig(updatedConfig);
            if (updatedTheme) {
                setTheme(updatedTheme);
            }
        },
        [],
    );

    const handleDismissDownload = useCallback((downloadId: string) => {
        setActiveDownloads((prev) => {
            const newMap = new Map(prev);
            newMap.delete(downloadId);
            return newMap;
        });
        dismissDownloadAPI(downloadId).catch((error) => {
            logger.error(`Failed to dismiss download ${downloadId} on backend:`, error);
        });
    }, []);

    const downloadSummaryStatus = useMemo((): DownloadSummaryStatus => {
        const statuses = Array.from(activeDownloads.values());
        if (statuses.length === 0) return 'idle';
        if (statuses.some((s) => s.status === 'error')) return 'error';
        if (statuses.some((s) => s.status === 'downloading' || s.status === 'pending'))
            return 'downloading';
        return 'completed';
    }, [activeDownloads]);

    const renderActiveTabContent = () => {
        if (isConfigLoading) {
            return <p className="loading-message">Loading configuration...</p>;
        }

        if (selectedModel) {
            return (
                <ModelDetailsPage
                    selectedModel={selectedModel}
                    onBack={handleBackToSearch}
                    openDownloadModal={openDownloadModal}
                />
            );
        }

        switch (activeTab) {
            case 'search':
                return (
                    <ModelSearchPage
                        onModelSelect={handleModelSelect}
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
                        uiStatuses={uiStatuses}
                    />
                );
            default:
                return (
                    <ModelSearchPage
                        onModelSelect={handleModelSelect}
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
                    // Pass the new props for the quick-start button
                    activeUiProfile={pathConfig?.uiProfile || null}
                    isUiRunning={activeUiProfileForStart?.is_running || false}
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

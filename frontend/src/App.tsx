// frontend/src/App.tsx
import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import './App.css';
import Navbar, { type MalTabKey } from './components/Layout/Navbar';
import ThemeSwitcher from './components/Theme/ThemeSwitcher';
import ModelSearchPage from './components/ModelLoader/ModelSearchPage';
import ModelDetailsPage from './components/ModelLoader/ModelDetailsPage';
import ConfigurationsPage from './components/Files/ConfigurationsPage';
import DownloadModal from './components/Downloads/DownloadModal';
// NEU: Wir importieren die neue Sidebar
import DownloadSidebar from './components/Downloads/DownloadSidebar';
import FileManagerPage from './components/FileManager/FileManagerPage';
import { dismissDownloadAPI } from './api/api';

import {
    // API and WebSocket functions
    getCurrentConfigurationAPI,
    configurePathsAPI,
    connectToDownloadTracker,
    // Types
    type PathConfigurationRequest,
    type ColorThemeType,
    type MalFullConfiguration,
    type ModelListItem,
    type ModelDetails,
    type ModelFile,
    type DownloadStatus,
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

// NEU: Ein Typ für den zusammengefassten Download-Status
export type DownloadSummaryStatus = 'idle' | 'downloading' | 'error' | 'completed';

function App() {
    const [pathConfig, setPathConfig] = useState<AppPathConfig | null>(null);
    const [theme, setTheme] = useState<ColorThemeType>('dark');
    const [activeTab, setActiveTab] = useState<MalTabKey>('search');
    const [isConfigLoading, setIsConfigLoading] = useState<boolean>(true);

    // --- State for Views ---
    const [selectedModel, setSelectedModel] = useState<ModelListItem | null>(null);

    // --- State for Download Modal ---
    const [isDownloadModalOpen, setIsDownloadModalOpen] = useState<boolean>(false);
    const [modelForDownload, setModelForDownload] = useState<ModelDetails | null>(null);
    const [specificFileForDownload, setSpecificFileForDownload] = useState<ModelFile | null>(null);

    // --- State for Download Tracking via WebSocket ---
    const [activeDownloads, setActiveDownloads] = useState<Map<string, DownloadStatus>>(new Map());
    
    // NEU: State für die Sichtbarkeit der Sidebar
    const [isDownloadsSidebarOpen, setDownloadsSidebarOpen] = useState(false);

    const ws = useRef<WebSocket | null>(null);

    useEffect(() => {
        if (!ws.current) {
            logger.info('Setting up WebSocket for download tracking...');
            const handleWsMessage = (data: any) => {
                // ... (WebSocket-Logik bleibt unverändert)
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

    // NEU: Handler, um die Sidebar zu öffnen/schließen
    const handleToggleDownloadsSidebar = useCallback(() => {
        setDownloadsSidebarOpen(prev => !prev);
    }, []);
    
    // NEU: Handler, um die Sidebar explizit zu schließen
    const handleCloseDownloadsSidebar = useCallback(() => {
        setDownloadsSidebarOpen(false);
    }, []);

    // NEU: Handler, der nach dem Starten von Downloads aufgerufen wird
    const handleDownloadsStarted = useCallback(() => {
        // Schließe das Modal und öffne die Sidebar
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

    const loadInitialConfig = useCallback(async () => {
        // ... (unverändert)
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
        } catch (error) {
            logger.error('Failed to load initial config from backend:', error);
        } finally {
            setIsConfigLoading(false);
        }
    }, []);

    useEffect(() => {
        loadInitialConfig();
    }, [loadInitialConfig]);

    useEffect(() => {
        document.body.className = theme === 'light' ? 'light-theme' : '';
    }, [theme]);

    const handleThemeToggleAndSave = useCallback(async () => {
        // ... (unverändert)
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
        // ... (unverändert)
        setActiveDownloads((prev) => {
            const newMap = new Map(prev);
            newMap.delete(downloadId);
            return newMap;
        });
        dismissDownloadAPI(downloadId).catch((error) => {
            logger.error(`Failed to dismiss download ${downloadId} on backend:`, error);
        });
    }, []);

    // NEU: Berechnet einen zusammengefassten Status für den Navbar-Button
    const downloadSummaryStatus = useMemo((): DownloadSummaryStatus => {
        const statuses = Array.from(activeDownloads.values());
        if (statuses.length === 0) return 'idle';
        if (statuses.some(s => s.status === 'error')) return 'error';
        if (statuses.some(s => s.status === 'downloading' || s.status === 'pending')) return 'downloading';
        // Wenn kein Fehler und nichts mehr läuft, dann muss alles fertig sein
        return 'completed';
    }, [activeDownloads]);

    const renderActiveTabContent = () => {
        // ... (unverändert)
        if (isConfigLoading) {
            return <p className="loading-message">Lade Konfiguration...</p>;
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
            case 'configuration':
                return (
                    <ConfigurationsPage
                        initialPathConfig={pathConfig}
                        onConfigurationSave={handlePathConfigurationUpdate}
                        currentGlobalTheme={theme}
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
        // NEU: Fügt eine Klasse hinzu, wenn die Sidebar offen ist, um den Hauptinhalt zu verschieben
        <div className={`app-wrapper ${isDownloadsSidebarOpen ? 'sidebar-open' : ''}`}>
            {/* ENTFERNT: Der alte DownloadManager ist weg */}
            {/* <DownloadManager activeDownloads={activeDownloads} onDismiss={handleDismissDownload} /> */}

            {/* NEU: Die neue DownloadSidebar wird hier gerendert */}
            <DownloadSidebar
                isOpen={isDownloadsSidebarOpen}
                onClose={handleCloseDownloadsSidebar}
                activeDownloads={activeDownloads}
                onDismiss={handleDismissDownload}
            />

            {/* Der Rest der App ist in einem eigenen Container, um ihn verschieben zu können */}
            <div className="app-content-pusher">
                <header className="app-header-placeholder">
                    <div style={{ gap: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <img src={appIcon} style={{ width: '2rem', height: 'auto' }} alt="M.A.L. Icon" />
                        <h1>M.A.L.</h1>
                    </div>
                </header>

                <Navbar
                    activeTab={activeTab}
                    onTabChange={(tab) => {
                        setSelectedModel(null);
                        setActiveTab(tab);
                    }}
                    // NEU: Props für den Download-Button
                    onToggleDownloads={handleToggleDownloadsSidebar}
                    downloadStatus={downloadSummaryStatus}
                    downloadCount={activeDownloads.size}
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
                // NEU: Callback, um die Sidebar zu öffnen
                onDownloadsStarted={handleDownloadsStarted}
            />
        </div>
    );
}

export default App;

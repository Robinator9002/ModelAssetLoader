// frontend/src/App.tsx
import { useState, useEffect, useCallback, useMemo } from 'react';
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

// --- Zustand Store Imports ---
// We now import our state management hooks. These will provide all the global state
// and actions needed by the application, replacing the local useState hooks.
import { useConfigStore, type AppPathConfig } from './state/configStore';
import { useUiStore } from './state/uiStore';
import { useTaskStore } from './state/taskStore';

// --- API & Type Imports ---
// We still need some types and direct API calls for actions triggered from this component.
import {
    installUiAPI,
    runUiAPI,
    stopUiAPI,
    deleteUiAPI,
    repairUiAPI,
    finalizeAdoptionAPI,
    type ModelListItem,
    type ModelDetails,
    type ModelFile,
    type UiNameType,
    type UiInstallRequest,
    type ColorThemeType,
} from './api/api';

/**
 * Represents the summarized status of all background tasks for UI feedback.
 */
export type DownloadSummaryStatus = 'idle' | 'downloading' | 'error' | 'completed';

/**
 * The root component of the M.A.L. application.
 *
 * REFACTOR NOTE: This component has been significantly simplified. It no longer manages
 * global application state directly. Instead, it consumes state from Zustand stores
 * and dispatches actions to them. Its primary responsibilities are now:
 * 1. Initializing the application state on mount (by calling store actions).
 * 2. Rendering the main layout (Navbar, Sidebar, etc.).
 * 3. Managing view-specific state that is NOT global (e.g., which modal is open).
 * 4. Acting as a bridge, passing state from stores as props to child components
 * that have not yet been refactored to use stores directly.
 */
function App() {
    // --- State from Zustand Stores ---
    // We pull all necessary global state directly from our stores.
    // This is declarative and ensures the component re-renders only when this specific state changes.
    const {
        pathConfig,
        theme,
        isLoading: isConfigLoading,
        loadInitialConfig,
        setTheme,
        updateConfiguration,
    } = useConfigStore();
    const { availableUis, uiStatuses, fetchUiData } = useUiStore();
    const { activeTasks, addTaskToAutoConfigure, connect, dismissTask } = useTaskStore();

    // --- Local View State ---
    // This state is truly local to App.tsx and manages what is currently being displayed.
    const [activeTab, setActiveTab] = useState<MalTabKey>('environments');
    const [selectedModel, setSelectedModel] = useState<ModelListItem | null>(null);
    const [isDownloadModalOpen, setIsDownloadModalOpen] = useState(false);
    const [modelForDownload, setModelForDownload] = useState<ModelDetails | null>(null);
    const [specificFileForDownload, setSpecificFileForDownload] = useState<ModelFile | null>(null);
    const [isDownloadsSidebarOpen, setDownloadsSidebarOpen] = useState(false);

    // --- Application Initialization Effect ---
    // This single useEffect is responsible for kicking off the application's data loading
    // and real-time connection setup by calling the actions from our stores.
    useEffect(() => {
        loadInitialConfig();
        fetchUiData();
        connect();
    }, [loadInitialConfig, fetchUiData, connect]);

    // --- Theme Management ---
    // This effect synchronizes the theme from the config store to the document body.
    useEffect(() => {
        document.body.className = theme === 'light' ? 'light-theme' : '';
    }, [theme]);

    // --- Action Handlers ---
    // These handlers are called by child components. They now trigger actions in our stores
    // or call the API, but no longer manage state with `useState`.

    const handlePathConfigurationUpdate = useCallback(
        (updatedConfig: AppPathConfig, updatedTheme: ColorThemeType) => {
            // The component receives the full config, but we only need to pass the request part.
            updateConfiguration({
                ...updatedConfig,
                profile: updatedConfig.uiProfile, // Aligning field names for the request
            });
            if (updatedTheme) setTheme(updatedTheme);
            fetchUiData(); // Refresh UI data in case the automatic UI changed
        },
        [updateConfiguration, setTheme, fetchUiData],
    );

    const handleInstallUi = useCallback(
        async (request: UiInstallRequest) => {
            try {
                const response = await installUiAPI(request);
                if (response.success && response.set_as_active_on_completion) {
                    addTaskToAutoConfigure(response.task_id);
                }
                setDownloadsSidebarOpen(true);
            } catch (error: any) {
                console.error(`Failed to start installation for ${request.ui_name}:`, error);
                // TODO: Implement a user-facing error notification system.
            }
        },
        [addTaskToAutoConfigure],
    );

    const handleRunUi = useCallback(async (uiName: UiNameType) => {
        try {
            await runUiAPI(uiName);
            setDownloadsSidebarOpen(true);
        } catch (error: any) {
            console.error(`Failed to start UI ${uiName}:`, error);
        }
    }, []);

    const handleStopUi = useCallback(async (taskId: string) => {
        try {
            await stopUiAPI(taskId);
        } catch (error: any) {
            console.error(`Failed to stop UI task ${taskId}:`, error);
        }
    }, []);

    const handleDeleteUi = useCallback(
        async (uiName: UiNameType) => {
            try {
                await deleteUiAPI(uiName);
                fetchUiData(); // Manually trigger a refresh after deletion.
            } catch (error: any) {
                console.error(`Failed to delete UI ${uiName}:`, error);
            }
        },
        [fetchUiData],
    );

    const handleRepairUi = useCallback(
        async (uiName: UiNameType, path: string, issuesToFix: string[]) => {
            try {
                const response = await repairUiAPI({
                    ui_name: uiName,
                    path,
                    issues_to_fix: issuesToFix,
                });
                if (response.success) {
                    addTaskToAutoConfigure(response.task_id);
                }
                setDownloadsSidebarOpen(true);
            } catch (error: any) {
                console.error(`Failed to start repair for ${uiName}:`, error);
            }
        },
        [addTaskToAutoConfigure],
    );

    const handleFinalizeAdoption = useCallback(
        async (uiName: UiNameType, path: string) => {
            try {
                await finalizeAdoptionAPI({ ui_name: uiName, path });
                fetchUiData(); // Refresh UI data after successful adoption.
            } catch (error: any) {
                console.error(`Failed to finalize adoption for ${uiName}:`, error);
            }
        },
        [fetchUiData],
    );

    const isUiBusy = useCallback(
        (uiName: UiNameType): boolean => {
            return Array.from(activeTasks.values()).some(
                (d) =>
                    d.filename === uiName && (d.status === 'pending' || d.status === 'downloading'),
            );
        },
        [activeTasks],
    );

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

    // --- Memoized Derived State ---
    // This logic derives simplified state from our stores to pass down as props.

    const downloadSummaryStatus = useMemo((): DownloadSummaryStatus => {
        const statuses = Array.from(activeTasks.values());
        if (statuses.length === 0) return 'idle';
        if (statuses.some((s) => s.status === 'error')) return 'error';
        if (statuses.some((s) => ['downloading', 'pending', 'running'].includes(s.status)))
            return 'downloading';
        return 'completed';
    }, [activeTasks]);

    const combinedManagedUis = useMemo(() => {
        const availableMap = new Map(availableUis.map((ui) => [ui.ui_name, ui]));
        return uiStatuses.map((status) => ({
            ...status,
            ...availableMap.get(status.ui_name),
        }));
    }, [availableUis, uiStatuses]);

    const activeUiForQuickStart = useMemo(() => {
        const targetUiName =
            pathConfig.configMode === 'automatic'
                ? pathConfig.automaticModeUi
                : pathConfig.uiProfile;
        if (!targetUiName || targetUiName === 'Custom') return null;
        return uiStatuses.find((s) => s.ui_name === targetUiName) || null;
    }, [pathConfig, uiStatuses]);

    const handleQuickStart = useCallback(() => {
        if (!activeUiForQuickStart) return;
        if (activeUiForQuickStart.is_running && activeUiForQuickStart.running_task_id) {
            handleStopUi(activeUiForQuickStart.running_task_id);
        } else if (activeUiForQuickStart.is_installed) {
            handleRunUi(activeUiForQuickStart.ui_name);
        }
    }, [activeUiForQuickStart, handleRunUi, handleStopUi]);

    // --- Render Logic ---

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
                onClose={() => setDownloadsSidebarOpen(false)}
                activeDownloads={activeTasks}
                onDismiss={dismissTask} // Pass the action from the store directly
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
                    onToggleDownloads={() => setDownloadsSidebarOpen((p) => !p)}
                    downloadStatus={downloadSummaryStatus}
                    downloadCount={activeTasks.size}
                    // --- FIX: Pass the corrected prop 'activeUiName' to the Navbar. ---
                    // This resolves the final TypeScript error by aligning the prop name
                    // with the updated NavbarProps interface.
                    activeUiName={activeUiForQuickStart?.ui_name || null}
                    isUiInstalled={activeUiForQuickStart?.is_installed || false}
                    isUiRunning={activeUiForQuickStart?.is_running || false}
                    onQuickStart={handleQuickStart}
                />
                <main className="main-content-area">{renderActiveTabContent()}</main>
            </div>
            <div className="theme-switcher-container">
                <ThemeSwitcher
                    currentTheme={theme}
                    onToggleTheme={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
                />
            </div>
            <DownloadModal
                isOpen={isDownloadModalOpen}
                onClose={() => setIsDownloadModalOpen(false)}
                modelDetails={modelForDownload}
                specificFileToDownload={specificFileForDownload}
                onDownloadsStarted={handleDownloadsStarted}
            />
        </div>
    );
}

export default App;

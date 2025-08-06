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
import { useConfigStore } from './state/configStore';
import { useUiStore } from './state/uiStore';
import { useTaskStore } from './state/taskStore';
// --- REFACTOR: Import the new modal store ---
import { useModalStore } from './state/modalStore';

// --- API & Type Imports ---
import { type ModelListItem } from './api/api';

/**
 * Represents the summarized status of all background tasks for UI feedback.
 */
export type DownloadSummaryStatus = 'idle' | 'downloading' | 'error' | 'completed';

/**
 * The root component of the M.A.L. application.
 *
 * @refactor This component has been significantly refactored. It no longer manages
 * the state for the Download Modal. That logic has been moved into a dedicated
 * `modalStore`. It also no longer contains the logic for its child pages, which
 * are now self-sufficient. Its primary role is now layout, routing, and wiring
 * up the remaining global components.
 */
function App() {
    // --- State from Zustand Stores ---
    const {
        pathConfig,
        theme,
        isLoading: isConfigLoading,
        loadInitialConfig,
        setTheme,
    } = useConfigStore();
    const { uiStatuses, fetchUiData } = useUiStore();
    const { activeTasks, connect, dismissTask } = useTaskStore();
    // --- REFACTOR: Get modal state directly from the modal store ---
    const { isDownloadModalOpen, modelForDownload, specificFileForDownload, closeDownloadModal } =
        useModalStore();

    // --- Local View State ---
    const [activeTab, setActiveTab] = useState<MalTabKey>('environments');
    const [selectedModel, setSelectedModel] = useState<ModelListItem | null>(null);
    const [isDownloadsSidebarOpen, setDownloadsSidebarOpen] = useState(false);

    // --- Application Initialization Effect ---
    useEffect(() => {
        loadInitialConfig();
        fetchUiData();
        connect();
    }, [loadInitialConfig, fetchUiData, connect]);

    // --- Theme Management ---
    useEffect(() => {
        document.body.className = theme === 'light' ? 'light-theme' : '';
    }, [theme]);

    // --- REFACTOR: This handler is now much simpler ---
    // It's only responsible for closing the modal (which is now done via the store)
    // and opening the sidebar.
    const handleDownloadsStarted = useCallback(() => {
        closeDownloadModal();
        setDownloadsSidebarOpen(true);
    }, [closeDownloadModal]);

    // --- Memoized Derived State ---
    const downloadSummaryStatus = useMemo((): DownloadSummaryStatus => {
        const statuses = Array.from(activeTasks.values());
        if (statuses.length === 0) return 'idle';
        if (statuses.some((s) => s.status === 'error')) return 'error';
        if (statuses.some((s) => ['downloading', 'pending', 'running'].includes(s.status)))
            return 'downloading';
        return 'completed';
    }, [activeTasks]);

    const activeUiForQuickStart = useMemo(() => {
        const targetUiName =
            pathConfig.configMode === 'automatic'
                ? pathConfig.automaticModeUi
                : pathConfig.uiProfile;
        if (!targetUiName || targetUiName === 'Custom') return null;
        return uiStatuses.find((s) => s.ui_name === targetUiName) || null;
    }, [pathConfig, uiStatuses]);

    // --- Render Logic ---

    const renderActiveTabContent = () => {
        if (isConfigLoading) {
            return <p className="page-state-container">Loading configuration...</p>;
        }
        if (selectedModel) {
            return (
                <ModelDetailsPage
                    selectedModel={selectedModel}
                    onBack={() => setSelectedModel(null)}
                />
            );
        }

        switch (activeTab) {
            case 'search':
                return <ModelSearchPage onModelSelect={setSelectedModel} />;
            case 'files':
                return <FileManagerPage />;
            case 'environments':
                return <UiManagementPage />;
            case 'configuration':
                return <ConfigurationsPage managedUis={uiStatuses} />;
            default:
                // Fallback to a default page
                return <UiManagementPage />;
        }
    };

    return (
        <div className={`app-wrapper ${isDownloadsSidebarOpen ? 'sidebar-open' : ''}`}>
            <DownloadSidebar
                isOpen={isDownloadsSidebarOpen}
                onClose={() => setDownloadsSidebarOpen(false)}
                activeDownloads={activeTasks}
                onDismiss={dismissTask}
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
                    activeUiName={activeUiForQuickStart?.ui_name || null}
                    isUiInstalled={activeUiForQuickStart?.is_installed || false}
                    isUiRunning={activeUiForQuickStart?.is_running || false}
                    // Quick start logic will be refactored later
                    onQuickStart={() => console.log('Quick Start Clicked')}
                />
                <main className="main-content-area">{renderActiveTabContent()}</main>
            </div>
            <div className="theme-switcher-container">
                <ThemeSwitcher
                    currentTheme={theme}
                    onToggleTheme={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
                />
            </div>
            {/* --- REFACTOR: The DownloadModal is now controlled by the modalStore --- */}
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

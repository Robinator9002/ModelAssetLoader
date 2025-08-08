// frontend/src/App.tsx
import { useState, useEffect, useCallback, useMemo } from 'react';
import { BrowserRouter, Routes, Route, useNavigate, Navigate } from 'react-router-dom';
import './App.css';

// --- Component Imports ---
import Navbar from './components/Layout/Navbar';
import ThemeSwitcher from './components/Switchers/ThemeSwitcher';
import ModelSearchPage from './components/ModelLoader/ModelSearchPage';
import ModelDetailsPage from './components/ModelLoader/ModelDetailsPage';
import ConfigurationsPage from './components/Files/ConfigurationsPage';
import DownloadModal from './components/Downloads/DownloadModal';
import DownloadSidebar from './components/Downloads/DownloadSidebar';
import FileManagerPage from './components/FileManager/FileManagerPage';
import UiManagementPage from './components/Environments/UiManagementPage';
import appIcon from '/icon.png';

// --- API & Store Imports ---
import { runUiAPI, stopUiAPI } from '~/api';
import { useConfigStore } from './state/configStore';
import { useUiStore } from './state/uiStore';
import { useTaskStore } from './state/taskStore';
import { useModalStore } from './state/modalStore';

export type DownloadSummaryStatus = 'idle' | 'downloading' | 'error' | 'completed';

function App() {
    return (
        <BrowserRouter>
            <AppContent />
        </BrowserRouter>
    );
}

function AppContent() {
    // --- Hooks ---
    const navigate = useNavigate();

    // --- State from Zustand Stores ---
    const {
        pathConfig,
        theme,
        isLoading: isConfigLoading,
        loadInitialConfig,
        setTheme,
    } = useConfigStore();
    const { uiStatuses, fetchUiData } = useUiStore();
    // --- PHASE 2.4 MODIFICATION: Get WebSocket status and the new initializer function ---
    const { activeTasks, wsStatus, initializeConnection, dismissTask } = useTaskStore();
    const { isDownloadModalOpen, modelForDownload, specificFileForDownload, closeDownloadModal } =
        useModalStore();

    // --- Local View State ---
    const [isDownloadsSidebarOpen, setDownloadsSidebarOpen] = useState(false);

    // --- Effects ---
    useEffect(() => {
        loadInitialConfig();
        fetchUiData();
        // --- PHASE 2.4 MODIFICATION: Use the robust connection initializer ---
        initializeConnection();
    }, [loadInitialConfig, fetchUiData, initializeConnection]);

    useEffect(() => {
        document.body.className = theme === 'light' ? 'light-theme' : '';
    }, [theme]);

    // --- Callbacks ---
    const handleDownloadsStarted = useCallback(() => {
        closeDownloadModal();
        setDownloadsSidebarOpen(true);
    }, [closeDownloadModal]);

    const handleBackToSearch = () => {
        navigate('/search');
    };

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
        if (pathConfig.configMode === 'automatic') {
            const targetId = pathConfig.automaticModeUi;
            if (!targetId) return null;
            return uiStatuses.find((s) => s.installation_id === targetId) || null;
        } else {
            const targetProfile = pathConfig.uiProfile;
            if (!targetProfile || targetProfile === 'Custom') return null;
            return uiStatuses.find((s) => s.ui_name === targetProfile) || null;
        }
    }, [pathConfig, uiStatuses]);

    const handleQuickStart = useCallback(() => {
        if (!activeUiForQuickStart) return;

        if (activeUiForQuickStart.is_running && activeUiForQuickStart.running_task_id) {
            console.log(`Stopping UI task: ${activeUiForQuickStart.running_task_id}`);
            stopUiAPI(activeUiForQuickStart.running_task_id).catch((err) =>
                console.error('Failed to stop UI via quick-start:', err),
            );
        } else if (activeUiForQuickStart.is_installed) {
            console.log(`Starting UI instance: ${activeUiForQuickStart.installation_id}`);
            runUiAPI(activeUiForQuickStart.installation_id).catch((err) =>
                console.error('Failed to start UI via quick-start:', err),
            );
        }
    }, [activeUiForQuickStart]);

    // --- Render Logic ---
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
                    <img src={appIcon} alt="M.A.L. Icon" />
                    <h1>M.A.L.</h1>
                </header>
                <Navbar
                    onToggleDownloads={() => setDownloadsSidebarOpen((p) => !p)}
                    downloadStatus={downloadSummaryStatus}
                    downloadCount={activeTasks.size}
                    activeUiName={activeUiForQuickStart?.display_name || null}
                    isUiInstalled={activeUiForQuickStart?.is_installed || false}
                    isUiRunning={activeUiForQuickStart?.is_running || false}
                    onQuickStart={handleQuickStart}
                    // --- PHASE 2.4 MODIFICATION: Pass the live WebSocket status to the Navbar ---
                    wsStatus={wsStatus}
                />
                <main className="main-content-area">
                    {isConfigLoading ? (
                        <p className="page-state-container">Loading configuration...</p>
                    ) : (
                        <Routes>
                            <Route path="/" element={<Navigate to="/search" replace />} />
                            <Route path="/search" element={<ModelSearchPage />} />
                            <Route
                                path="/search/:source/*"
                                element={<ModelDetailsPage onBack={handleBackToSearch} />}
                            />
                            <Route path="/files" element={<FileManagerPage />} />
                            <Route path="/environments" element={<UiManagementPage />} />
                            <Route
                                path="/configuration"
                                element={<ConfigurationsPage managedUis={uiStatuses} />}
                            />
                            <Route path="*" element={<Navigate to="/search" replace />} />
                        </Routes>
                    )}
                </main>
            </div>
            <div className="theme-switcher-container">
                <ThemeSwitcher
                    currentTheme={theme}
                    onToggleTheme={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
                />
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

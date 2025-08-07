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

// --- Zustand Store Imports ---
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
    const { activeTasks, connect, dismissTask } = useTaskStore();
    const { isDownloadModalOpen, modelForDownload, specificFileForDownload, closeDownloadModal } =
        useModalStore();

    // --- Local View State ---
    const [isDownloadsSidebarOpen, setDownloadsSidebarOpen] = useState(false);

    // --- Effects ---
    useEffect(() => {
        loadInitialConfig();
        fetchUiData();
        connect();
    }, [loadInitialConfig, fetchUiData, connect]);

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
        const targetUiName =
            pathConfig.configMode === 'automatic'
                ? pathConfig.automaticModeUi
                : pathConfig.uiProfile;
        if (!targetUiName || targetUiName === 'Custom') return null;
        return uiStatuses.find((s) => s.ui_name === targetUiName) || null;
    }, [pathConfig, uiStatuses]);

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
                    <img
                        src={appIcon}
                        style={{ width: '2rem', height: 'auto' }}
                        alt="M.A.L. Icon"
                    />
                    <h1>M.A.L.</h1>
                </header>
                <Navbar
                    onToggleDownloads={() => setDownloadsSidebarOpen((p) => !p)}
                    downloadStatus={downloadSummaryStatus}
                    downloadCount={activeTasks.size}
                    activeUiName={activeUiForQuickStart?.ui_name || null}
                    isUiInstalled={activeUiForQuickStart?.is_installed || false}
                    isUiRunning={activeUiForQuickStart?.is_running || false}
                    onQuickStart={() => console.log('Quick Start Clicked')}
                />
                <main className="main-content-area">
                    {isConfigLoading ? (
                        <p className="page-state-container">Loading configuration...</p>
                    ) : (
                        <Routes>
                            <Route path="/" element={<Navigate to="/search" replace />} />
                            <Route path="/search" element={<ModelSearchPage />} />

                            {/* --- FIX: Use a splat (*) route to capture multi-segment model IDs --- */}
                            {/* This tells the router to match `/search/:source/` and then treat the rest of the URL */}
                            {/* as a single parameter, correctly handling IDs like `google/gemma-7b`. */}
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

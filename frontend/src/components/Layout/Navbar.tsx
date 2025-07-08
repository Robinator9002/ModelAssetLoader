// frontend/src/components/Layout/Navbar.tsx
import React from 'react';
import {
    Search,
    Settings,
    FolderKanban,
    DownloadCloud,
    CheckCircle2,
    AlertTriangle,
    Loader2,
    Layers,
    Play,
    Power,
} from 'lucide-react';
import { type DownloadSummaryStatus } from '../../App';
import { type UiProfileType } from '../../api/api';

export type MalTabKey = 'search' | 'files' | 'configuration' | 'environments';

interface NavbarProps {
    activeTab: MalTabKey;
    onTabChange: (tab: MalTabKey) => void;
    onToggleDownloads: () => void;
    downloadStatus: DownloadSummaryStatus;
    downloadCount: number;
    // Props for the new quick-start button
    activeUiProfile: UiProfileType | null;
    isUiInstalled: boolean; // --- FIX: Added this prop ---
    isUiRunning: boolean;
    onQuickStart: () => void;
}

interface NavItemConfig {
    key: MalTabKey;
    label: string;
    icon: React.ReactNode;
}

const navItems: NavItemConfig[] = [
    {
        key: 'search',
        label: 'Model Search',
        icon: <Search size={18} />,
    },
    {
        key: 'files',
        label: 'File Manager',
        icon: <FolderKanban size={18} />,
    },
    {
        key: 'environments',
        label: 'UI Management',
        icon: <Layers size={18} />,
    },
    {
        key: 'configuration',
        label: 'Settings',
        icon: <Settings size={18} />,
    },
];

/**
 * The main navigation bar for the application. It displays the primary navigation
 * tabs and provides a dynamic button to manage and view the status of downloads.
 */
const Navbar: React.FC<NavbarProps> = ({
    activeTab,
    onTabChange,
    onToggleDownloads,
    downloadStatus,
    downloadCount,
    activeUiProfile,
    isUiInstalled, // --- FIX: Destructured the new prop ---
    isUiRunning,
    onQuickStart,
}) => {
    /**
     * Determines which icon to display on the downloads button based on the
     * summarized status of all active downloads.
     */
    const getDownloadStatusIcon = () => {
        switch (downloadStatus) {
            case 'downloading':
                return <Loader2 size={18} className="animate-spin" />;
            case 'completed':
                return <CheckCircle2 size={18} />;
            case 'error':
                return <AlertTriangle size={18} />;
            default: // 'idle'
                return <DownloadCloud size={18} />;
        }
    };

    // --- FIX: The condition now checks if the UI is installed before rendering the button ---
    const showQuickStartButton = activeUiProfile && activeUiProfile !== 'Custom' && isUiInstalled;

    return (
        <header className="app-navbar">
            <nav className="navbar-tabs-nav">
                <ul className="navbar-tabs-list">
                    {navItems.map((item) => (
                        <li key={item.key} className="navbar-tab-item">
                            <button
                                className={`navbar-tab-button ${
                                    activeTab === item.key ? 'active' : ''
                                }`}
                                onClick={() => onTabChange(item.key)}
                                aria-current={activeTab === item.key ? 'page' : undefined}
                                title={item.label}
                            >
                                <span className="navbar-tab-icon">{item.icon}</span>
                                <span className="navbar-tab-label">{item.label}</span>
                            </button>
                        </li>
                    ))}
                </ul>
            </nav>

            <div className="navbar-actions">
                {showQuickStartButton && (
                    <button
                        className={`quick-start-button ${isUiRunning ? 'running' : 'stopped'}`}
                        onClick={onQuickStart}
                        title={isUiRunning ? `Stop ${activeUiProfile}` : `Start ${activeUiProfile}`}
                    >
                        {isUiRunning ? (
                            <Loader2 size={16} className="animate-spin" />
                        ) : (
                            <Play size={16} />
                        )}
                        <span className="quick-start-label">{activeUiProfile}</span>
                        <Power size={16} />
                    </button>
                )}

                <button
                    className={`download-status-button ${downloadStatus}`}
                    onClick={onToggleDownloads}
                    title="Show Downloads"
                    disabled={downloadCount === 0 && downloadStatus === 'idle'}
                >
                    <span className="download-status-icon">{getDownloadStatusIcon()}</span>
                    <span className="navbar-tab-label">Downloads</span>
                    {downloadCount > 0 && (
                        <span className="download-count-badge">{downloadCount}</span>
                    )}
                </button>
            </div>
        </header>
    );
};

export default Navbar;

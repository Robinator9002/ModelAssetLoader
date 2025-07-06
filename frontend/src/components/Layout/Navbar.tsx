// frontend/src/components/Layout/Navbar.tsx
import React from 'react';
import { Search, Settings, FolderKanban, DownloadCloud, CheckCircle2, AlertTriangle, Loader2, Layers } from 'lucide-react';
import { type DownloadSummaryStatus } from '../../App';

// Add the new 'environments' key for the new tab.
export type MalTabKey = 'search' | 'files' | 'configuration' | 'environments';

interface NavbarProps {
    activeTab: MalTabKey;
    onTabChange: (tab: MalTabKey) => void;
    onToggleDownloads: () => void;
    downloadStatus: DownloadSummaryStatus;
    downloadCount: number;
}

interface NavItemConfig {
    key: MalTabKey;
    label: string;
    icon: React.ReactNode;
}

// Define the configuration for all navigation items, including the new one.
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
    downloadCount
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
                <button 
                    className={`download-status-button ${downloadStatus}`}
                    onClick={onToggleDownloads}
                    title="Show Downloads"
                    disabled={downloadCount === 0 && downloadStatus === 'idle'}
                >
                    <span className="download-status-icon">
                        {getDownloadStatusIcon()}
                    </span>
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

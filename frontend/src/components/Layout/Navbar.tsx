// frontend/src/components/Layout/Navbar.tsx
import React from 'react';
import { Search, Settings, FolderKanban, DownloadCloud, CheckCircle2, AlertTriangle, Loader2 } from 'lucide-react';
import { type DownloadSummaryStatus } from '../../App';

// The type definition for the available tabs in the application.
export type MalTabKey = 'search' | 'files' | 'configuration';

interface NavbarProps {
    activeTab: MalTabKey;
    onTabChange: (tab: MalTabKey) => void;
    // NEU: Props für den Download-Button
    onToggleDownloads: () => void;
    downloadStatus: DownloadSummaryStatus;
    downloadCount: number;
}

interface NavItemConfig {
    key: MalTabKey;
    label: string;
    icon: React.ReactNode;
}

// Configuration for the navigation items, now using Lucide icons.
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
        key: 'configuration',
        label: 'Configuration',
        icon: <Settings size={18} />,
    },
];

const Navbar: React.FC<NavbarProps> = ({ 
    activeTab, 
    onTabChange,
    onToggleDownloads,
    downloadStatus,
    downloadCount
}) => {

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

            {/* NEU: Container für Aktionen auf der rechten Seite */}
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

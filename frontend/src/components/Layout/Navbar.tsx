// frontend/src/components/Layout/Navbar.tsx
import React from 'react';
import { NavLink } from 'react-router-dom';
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

export interface NavItemConfig {
    key: string;
    label: string;
    icon: React.ReactNode;
}

const navItems: NavItemConfig[] = [
    { key: '/environments', label: 'UI Management', icon: <Layers size={18} /> },
    { key: '/search', label: 'Model Search', icon: <Search size={18} /> },
    { key: '/files', label: 'File Manager', icon: <FolderKanban size={18} /> },
    { key: '/configuration', label: 'Settings', icon: <Settings size={18} /> },
];

/**
 * @refactor This component has been updated for react-router-dom.
 * It no longer takes `activeTab` or `onTabChange` props. Instead, it uses
 * the `NavLink` component, which automatically handles the 'active' state
 * based on the current URL, fully decoupling navigation from App.tsx.
 */
interface NavbarProps {
    onToggleDownloads: () => void;
    downloadStatus: DownloadSummaryStatus;
    downloadCount: number;
    /**
     * @fix {TYPESCRIPT} Changed type from `UiNameType | null` to `string | null`.
     * This is the fix for the TypeScript error. The quick-start button now correctly
     * accepts any user-defined `display_name` string, not just the restrictive enum.
     */
    activeUiName: string | null;
    isUiInstalled: boolean;
    isUiRunning: boolean;
    onQuickStart: () => void;
}

const Navbar: React.FC<NavbarProps> = ({
    onToggleDownloads,
    downloadStatus,
    downloadCount,
    activeUiName,
    isUiInstalled,
    isUiRunning,
    onQuickStart,
}) => {
    const getDownloadStatusIcon = () => {
        switch (downloadStatus) {
            case 'downloading':
                return <Loader2 size={18} className="animate-spin" />;
            case 'completed':
                return <CheckCircle2 size={18} />;
            case 'error':
                return <AlertTriangle size={18} />;
            default:
                return <DownloadCloud size={18} />;
        }
    };

    const showQuickStartButton = activeUiName && isUiInstalled;

    return (
        <header className="app-navbar">
            <nav className="navbar-tabs-nav">
                <ul className="navbar-tabs-list">
                    {navItems.map((item) => (
                        <li key={item.key} className="navbar-tab-item">
                            <NavLink
                                to={item.key}
                                className={({ isActive }) =>
                                    `navbar-tab-button ${isActive ? 'active' : ''}`
                                }
                                title={item.label}
                            >
                                <span className="navbar-tab-icon">{item.icon}</span>
                                <span className="navbar-tab-label">{item.label}</span>
                            </NavLink>
                        </li>
                    ))}
                </ul>
            </nav>

            <div className="navbar-actions">
                {showQuickStartButton && (
                    <button
                        className={`quick-start-button ${isUiRunning ? 'running' : 'stopped'}`}
                        onClick={onQuickStart}
                        title={isUiRunning ? `Stop ${activeUiName}` : `Start ${activeUiName}`}
                    >
                        {isUiRunning ? (
                            <Loader2 size={16} className="animate-spin" />
                        ) : (
                            <Play size={16} />
                        )}
                        <span className="quick-start-label">{activeUiName}</span>
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

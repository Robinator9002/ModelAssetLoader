// frontend/src/components/Layout/Navbar.tsx
import React from "react";
import { Search, Settings, FolderKanban } from "lucide-react";

// The type definition for the available tabs in the application.
export type MalTabKey = "search" | "files" | "configuration";

interface NavbarProps {
	activeTab: MalTabKey;
	onTabChange: (tab: MalTabKey) => void;
}

interface NavItemConfig {
	key: MalTabKey;
	label: string;
	icon: React.ReactNode;
}

// Configuration for the navigation items, now using Lucide icons.
const navItems: NavItemConfig[] = [
	{
		key: "search",
		label: "Model Search",
		icon: <Search size={18} />,
	},
    {
        key: "files",
        label: "File Manager",
        icon: <FolderKanban size={18} />
    },
	{
		key: "configuration",
		label: "Configuration",
		icon: <Settings size={18} />,
	},
];

const Navbar: React.FC<NavbarProps> = ({ activeTab, onTabChange }) => {
	return (
		<header className="app-navbar">
            <div className="navbar-brand">
                <strong>M.A.L.</strong>
            </div>
			<nav className="navbar-tabs-nav">
                <ul className="navbar-tabs-list">
                    {navItems.map((item) => (
                        <li key={item.key} className="navbar-tab-item">
                            <button
                                className={`navbar-tab-button ${
                                    activeTab === item.key ? "active" : ""
                                }`}
                                onClick={() => onTabChange(item.key)}
                                aria-current={activeTab === item.key ? "page" : undefined}
                                title={item.label}
                            >
                                <span className="navbar-tab-icon">{item.icon}</span>
                                <span className="navbar-tab-label">{item.label}</span>
                            </button>
                        </li>
                    ))}
                </ul>
            </nav>
		</header>
	);
};

export default Navbar;

// frontend/src/components/Layout/Navbar.tsx
import React from "react";
// Das CSS wird über App.css importiert: @import url('../../style/Layout/Navbar.css');

// Definiere die möglichen Tabs/Ansichten für M.A.L.
// Dieser Typ wird auch in App.tsx verwendet.
export type MalTabKey = "search" | "configuration"; // | "downloads" // "downloads" für später

interface NavbarProps {
	activeTab: MalTabKey;
	onTabChange: (tab: MalTabKey) => void;
}

interface NavItemConfig {
	key: MalTabKey;
	label: string;
	icon?: JSX.Element;
}

// Konfiguration der Navigations-Items für M.A.L.
const navItems: NavItemConfig[] = [
	{
		key: "search",
		label: "Modellsuche",
		icon: (
			<svg
				xmlns="http://www.w3.org/2000/svg"
				width="18"
				height="18"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				strokeWidth="2"
				strokeLinecap="round"
				strokeLinejoin="round"
			>
				<circle cx="11" cy="11" r="8"></circle>
				<line x1="21" y1="21" x2="16.65" y2="16.65"></line>
			</svg>
		),
	},
	{
		key: "configuration",
		label: "Konfiguration",
		icon: (
			<svg
				xmlns="http://www.w3.org/2000/svg"
				width="18"
				height="18"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				strokeWidth="2"
				strokeLinecap="round"
				strokeLinejoin="round"
			>
				<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.38a2 2 0 0 0-.73-2.73l-.15-.1a2 2 0 0 1-1-1.72v-.51a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"></path>
				<circle cx="12" cy="12" r="3"></circle>
			</svg>
		),
	},
	// {
	//   key: "downloads", // Für später
	//   label: "Downloads",
	//   icon: <svg>...</svg>,
	// },
];

const Navbar: React.FC<NavbarProps> = ({ activeTab, onTabChange }) => {
	return (
		<nav className="app-navbar">
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
							{item.icon && (
								<span className="navbar-tab-icon">{item.icon}</span>
							)}
							<span className="navbar-tab-label">{item.label}</span>
						</button>
					</li>
				))}
			</ul>
		</nav>
	);
};

export default Navbar;

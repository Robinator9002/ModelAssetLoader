// frontend/src/components/Files/AutomaticModeSettings.tsx
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { type UiNameType, type UiProfileType, type ManagedUiStatus } from '~/api';
import { Layers, CheckCircle, Download } from 'lucide-react';

// --- Component Props ---
interface AutomaticModeSettingsProps {
    /** List of all managed UIs that have been successfully installed. */
    installedUis: (ManagedUiStatus & { default_profile_name?: UiProfileType })[];
    /** The name of the currently selected UI in automatic mode. */
    selectedManagedUi: UiNameType | null;
    /** Callback function to notify the parent when a UI is selected. */
    onSelectUi: (ui: ManagedUiStatus & { default_profile_name?: UiProfileType }) => void;
}

/**
 * A specialized component for handling the "Automatic" configuration mode.
 *
 * @refactor This component now includes a user-friendly, guided empty state
 * that appears when no managed UIs are installed. This state provides a clear
 * call-to-action, directing the user to the Environments page.
 */
const AutomaticModeSettings: React.FC<AutomaticModeSettingsProps> = ({
    installedUis,
    selectedManagedUi,
    onSelectUi,
}) => {
    // --- NEW: Add the navigate hook for the call-to-action button ---
    const navigate = useNavigate();

    // --- RENDER LOGIC ---

    // If no UIs are installed, render the new empty state call-to-action.
    if (installedUis.length === 0) {
        return (
            <div className="config-empty-state">
                <Layers size={48} className="empty-state-icon" />
                <h3 className="empty-state-title">No Managed UIs Found</h3>
                <p className="empty-state-text">
                    To use Automatic Mode, you first need to install an AI Environment. This will
                    allow M.A.L. to manage all paths for you.
                </p>
                <button
                    className="button button-primary empty-state-button"
                    onClick={() => navigate('/environments')}
                >
                    <Download size={18} />
                    Install an Environment
                </button>
            </div>
        );
    }

    // If UIs are installed, render the standard selection UI.
    return (
        <>
            <label className="config-label">
                Select a M.A.L.-managed UI. Its folder will be automatically used as the base path.
            </label>
            <div className="profile-selector-grid">
                {installedUis.map((ui) => (
                    <div
                        key={ui.ui_name}
                        className={`profile-card ${
                            selectedManagedUi === ui.ui_name ? 'selected' : ''
                        }`}
                        onClick={() => onSelectUi(ui)}
                        tabIndex={0}
                        role="radio"
                        aria-checked={selectedManagedUi === ui.ui_name}
                        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onSelectUi(ui)}
                    >
                        <span className="profile-card-icon">
                            {selectedManagedUi === ui.ui_name ? (
                                <CheckCircle size={32} />
                            ) : (
                                <Layers size={32} />
                            )}
                        </span>
                        <span className="profile-card-name">{ui.ui_name}</span>
                        <span className="profile-card-tag">Managed</span>
                    </div>
                ))}
            </div>
        </>
    );
};

export default AutomaticModeSettings;

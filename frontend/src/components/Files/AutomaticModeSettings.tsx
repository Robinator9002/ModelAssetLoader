// frontend/src/components/Files/AutomaticModeSettings.tsx
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { type ManagedUiStatus } from '~/api';
import { Layers, CheckCircle, Download } from 'lucide-react';

// --- Component Props ---
/**
 * @refactor {CRITICAL} The props interface has been updated.
 * - `selectedManagedUi` (by name) is now `selectedManagedUiId` (by unique ID).
 * - The `onSelectUi` callback now correctly passes the full `ManagedUiStatus` object.
 * - The type for `installedUis` is simplified as it no longer needs a merged-in property.
 */
interface AutomaticModeSettingsProps {
    /** List of all managed UIs that have been successfully installed. */
    installedUis: ManagedUiStatus[];
    /** The unique ID of the currently selected UI instance in automatic mode. */
    selectedManagedUiId: string | null;
    /** Callback function to notify the parent when a UI instance is selected. */
    onSelectUi: (ui: ManagedUiStatus) => void;
}

/**
 * A specialized component for handling the "Automatic" configuration mode.
 * It now correctly operates on unique UI instances using their `installation_id`.
 */
const AutomaticModeSettings: React.FC<AutomaticModeSettingsProps> = ({
    installedUis,
    selectedManagedUiId,
    onSelectUi,
}) => {
    const navigate = useNavigate();

    // If no UIs are installed, render a user-friendly, guided empty state.
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
                Select a M.A.L.-managed UI instance. Its folder will be automatically used as the
                base path.
            </label>
            <div className="profile-selector-grid">
                {installedUis.map((ui) => {
                    // --- FIX: The selection check is now based on the unique `installation_id` ---
                    const isSelected = selectedManagedUiId === ui.installation_id;
                    return (
                        <div
                            // --- FIX: The key is now the unique `installation_id` ---
                            key={ui.installation_id}
                            className={`profile-card ${isSelected ? 'selected' : ''}`}
                            onClick={() => onSelectUi(ui)}
                            tabIndex={0}
                            role="radio"
                            aria-checked={isSelected}
                            onKeyDown={(e) =>
                                (e.key === 'Enter' || e.key === ' ') && onSelectUi(ui)
                            }
                        >
                            <span className="profile-card-icon">
                                {isSelected ? <CheckCircle size={32} /> : <Layers size={32} />}
                            </span>
                            {/* --- FIX: Display the user-provided `display_name` --- */}
                            <span className="profile-card-name">{ui.display_name}</span>
                            <span className="profile-card-tag">{ui.ui_name}</span>
                        </div>
                    );
                })}
            </div>
        </>
    );
};

export default AutomaticModeSettings;

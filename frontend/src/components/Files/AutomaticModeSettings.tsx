// frontend/src/components/Files/AutomaticModeSettings.tsx
import React from 'react';
import { type UiNameType, type UiProfileType, type ManagedUiStatus } from '~/api';
import { Layers, CheckCircle, Info } from 'lucide-react';

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
 * This component was extracted from the larger ConfigurationsPage to encapsulate
 * all logic and rendering related to selecting a managed UI. It receives the list
 * of installed UIs and reports the user's selection back to its parent.
 */
const AutomaticModeSettings: React.FC<AutomaticModeSettingsProps> = ({
    installedUis,
    selectedManagedUi,
    onSelectUi,
}) => {
    return (
        <>
            <label className="config-label">
                Select a M.A.L.-managed UI. Its folder will be automatically used as the base path.
            </label>
            {installedUis.length > 0 ? (
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
                            onKeyDown={(e) =>
                                (e.key === 'Enter' || e.key === ' ') && onSelectUi(ui)
                            }
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
            ) : (
                <div className="info-box">
                    <Info size={24} className="icon" />
                    <span>
                        No managed UIs found. Install one from the 'Environments' tab, or switch to{' '}
                        <strong>Manual</strong> mode.
                    </span>
                </div>
            )}
        </>
    );
};

export default AutomaticModeSettings;

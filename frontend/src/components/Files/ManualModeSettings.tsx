// frontend/src/components/Files/ManualModeSettings.tsx
import React, { useState } from 'react';
import { type UiProfileType } from '../../api/api';
import FolderSelector from './FolderSelector';

// --- Component Props ---
interface ManualModeSettingsProps {
    /** The currently configured manual base path. */
    manualBasePath: string | null;
    /** The currently selected UI profile. */
    selectedProfile: UiProfileType | null;
    /** Callback to notify the parent of a base path change. */
    onBasePathChange: (path: string | null) => void;
    /** Callback to notify the parent of a profile change. */
    onProfileChange: (profile: UiProfileType | null) => void;
}

/**
 * A specialized component for handling the "Manual" configuration mode.
 *
 * This component was extracted from ConfigurationsPage to encapsulate all
 * logic related to manually selecting a base folder and a corresponding
 * UI profile. It manages the state for the FolderSelector modal.
 */
const ManualModeSettings: React.FC<ManualModeSettingsProps> = ({
    manualBasePath,
    selectedProfile,
    onBasePathChange,
    onProfileChange,
}) => {
    // --- Local View State ---
    const [isFolderSelectorOpen, setIsFolderSelectorOpen] = useState(false);

    // --- Event Handlers ---
    const handleSelectPath = (path: string) => {
        onBasePathChange(path);
        // When a new base path is selected, force the user to re-select a profile
        // to ensure path suggestions are correctly re-evaluated.
        onProfileChange(null);
        setIsFolderSelectorOpen(false);
    };

    return (
        <>
            {/* --- Base Path Selection --- */}
            <div className="config-card">
                <h2 className="config-card-header">Step 1: Select Base Folder</h2>
                <div className="config-card-body">
                    <section className="config-section">
                        <label htmlFor="basePathDisplay" className="config-label">
                            Select the main folder where your models are stored.
                        </label>
                        <div className="base-path-selector">
                            <input
                                type="text"
                                id="basePathDisplay"
                                value={manualBasePath || 'Click "Browse" to select a folder...'}
                                readOnly
                                className="config-input path-input"
                                onClick={() => setIsFolderSelectorOpen(true)}
                                title={manualBasePath || 'Click to select base folder'}
                            />
                            <button
                                onClick={() => setIsFolderSelectorOpen(true)}
                                className="button"
                            >
                                Browse...
                            </button>
                        </div>
                    </section>
                </div>
            </div>

            {/* --- UI Profile Selection --- */}
            <div className={`config-card ${!manualBasePath ? 'disabled-card' : ''}`}>
                <h2 className="config-card-header">Step 2: Select UI Profile</h2>
                <div className="config-card-body">
                    <section className="config-section">
                        <label htmlFor="uiProfileSelect" className="config-label">
                            Choose the profile that matches your UI's folder structure for the best
                            path suggestions.
                        </label>
                        <select
                            id="uiProfileSelect"
                            value={selectedProfile || ''}
                            onChange={(e) => onProfileChange(e.target.value as UiProfileType)}
                            className="config-select"
                        >
                            <option value="" disabled>
                                Select a profile type...
                            </option>
                            <option value="ComfyUI">ComfyUI</option>
                            <option value="A1111">A1111 / Forge</option>
                            <option value="Custom">Custom (Advanced)</option>
                        </select>
                    </section>
                </div>
            </div>

            {/* --- Modals --- */}
            <FolderSelector
                isOpen={isFolderSelectorOpen}
                onSelectFinalPath={handleSelectPath}
                onCancel={() => setIsFolderSelectorOpen(false)}
            />
        </>
    );
};

export default ManualModeSettings;

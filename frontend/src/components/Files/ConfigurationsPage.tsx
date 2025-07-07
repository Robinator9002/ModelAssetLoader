// frontend/src/components/Files/ConfigurationsPage.tsx
import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
    configurePathsAPI,
    type PathConfigurationRequest,
    type UiProfileType,
    type ModelType,
    type ColorThemeType,
    type ManagedUiStatus,
    type ConfigurationMode,
} from '../../api/api';
import type { AppPathConfig } from '../../App';
import FolderSelector from './FolderSelector';
import {
    Folder,
    Settings,
    Save,
    AlertTriangle,
    Layers,
    SlidersHorizontal,
    Info,
    CheckCircle,
    PackageCheck,
    MousePointerClick,
} from 'lucide-react';

// A frontend copy of the backend's known UI profiles for instant path suggestions.
const KNOWN_UI_PROFILES: Record<string, Record<string, string>> = {
    ComfyUI: {
        checkpoints: 'models/checkpoints',
        loras: 'models/loras',
        vae: 'models/vae',
        clip: 'models/clip',
        controlnet: 'models/controlnet',
        embeddings: 'models/embeddings',
        diffusers: 'models/diffusers',
        unet: 'models/unet',
        hypernetworks: 'models/hypernetworks',
    },
    A1111: {
        checkpoints: 'models/Stable-diffusion',
        loras: 'models/Lora',
        vae: 'models/VAE',
        embeddings: 'embeddings',
        hypernetworks: 'models/hypernetworks',
        controlnet: 'models/ControlNet',
    },
    ForgeUI: {
        checkpoints: 'models/Stable-diffusion',
        loras: 'models/Lora',
        vae: 'models/VAE',
        embeddings: 'embeddings',
        hypernetworks: 'models/hypernetworks',
        controlnet: 'models/ControlNet',
    },
};

// Defines the properties for the ConfigurationsPage component.
interface ConfigurationsPageProps {
    initialPathConfig: AppPathConfig;
    onConfigurationSave: (savedConfig: AppPathConfig, savedTheme: ColorThemeType) => void;
    currentGlobalTheme: ColorThemeType;
    uiStatuses: ManagedUiStatus[];
    initialConfigMode: ConfigurationMode;
}

/**
 * A comprehensive settings page for configuring the application's core functionalities,
 * including file paths and UI integration modes.
 */
const ConfigurationsPage: React.FC<ConfigurationsPageProps> = ({
    initialPathConfig,
    onConfigurationSave,
    currentGlobalTheme,
    uiStatuses,
    initialConfigMode,
}) => {
    // --- Component State ---
    const [configMode, setConfigMode] = useState<ConfigurationMode>(initialConfigMode);
    const [basePath, setBasePath] = useState<string | null>(initialPathConfig.basePath);
    const [selectedProfile, setSelectedProfile] = useState<UiProfileType | null>(
        initialPathConfig.uiProfile,
    );
    const [modelPaths, setModelPaths] = useState<Partial<Record<ModelType, string>>>(
        initialPathConfig.customPaths,
    );
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(
        null,
    );
    const [isFolderSelectorOpen, setIsFolderSelectorOpen] = useState(false);

    // --- Refs for UI Effects ---
    const modeSwitcherRef = useRef<HTMLDivElement>(null);
    const highlightRef = useRef<HTMLDivElement>(null);

    // --- Effects ---

    // Synchronize component state with initial props from App.tsx.
    useEffect(() => {
        setBasePath(initialPathConfig.basePath || null);
        setSelectedProfile(initialPathConfig.uiProfile || null);
        setModelPaths(initialPathConfig.customPaths || {});
        setConfigMode(initialConfigMode);
    }, [initialPathConfig, initialConfigMode]);

    // Animate the mode switcher's highlight bar when the mode changes.
    useEffect(() => {
        if (modeSwitcherRef.current && highlightRef.current) {
            const activeOption = modeSwitcherRef.current.querySelector(
                '.mode-switch-option.active',
            ) as HTMLElement;
            if (activeOption) {
                const highlight = highlightRef.current;
                highlight.style.left = `${activeOption.offsetLeft}px`;
                highlight.style.width = `${activeOption.offsetWidth}px`;
            }
        }
    }, [configMode]);

    // --- Memoized Values ---

    const installedUis = useMemo(
        () => uiStatuses.filter((status) => status.is_installed),
        [uiStatuses],
    );

    const modelTypesForPaths: ModelType[] = useMemo(
        () =>
            [
                'checkpoints',
                'loras',
                'vae',
                'embeddings',
                'controlnet',
                'diffusers',
                'clip',
                'unet',
                'hypernetworks',
            ].sort() as ModelType[],
        [],
    );

    // --- Event Handlers ---

    /**
     * Handles the selection of a UI profile. It sets the profile name and
     * automatically populates the model paths based on known defaults.
     * @param profile The name of the selected UI profile.
     */
    const handleProfileSelect = useCallback((profile: UiProfileType | null) => {
        setSelectedProfile(profile);
        if (profile && profile !== 'Custom') {
            const defaultPaths = KNOWN_UI_PROFILES[profile] || {};
            setModelPaths(defaultPaths);
        } else if (profile === 'Custom') {
            // Clear paths for custom to avoid carrying over old settings
            setModelPaths({});
        }
    }, []);

    /**
     * Updates the path for a specific model type.
     * @param modelType The type of model (e.g., 'loras').
     * @param value The new relative path for that model type.
     */
    const handleModelPathChange = useCallback((modelType: ModelType, value: string) => {
        setModelPaths((prev) => ({ ...prev, [modelType]: value.trim() }));
    }, []);

    /**
     * Switches the configuration mode and resets dependent state to ensure a clean slate.
     * @param mode The new configuration mode ('automatic' or 'manual').
     */
    const handleModeChange = (mode: ConfigurationMode) => {
        setConfigMode(mode);
        // Reset selections when switching modes to prevent invalid states
        handleProfileSelect(null);
    };

    /**
     * Gathers all configuration data, sends it to the backend API for saving,
     * and communicates the result back to the parent component.
     */
    const handleSaveConfiguration = useCallback(async () => {
        if (!basePath) {
            setFeedback({ type: 'error', message: 'A base storage location must be selected.' });
            return;
        }
        if (!selectedProfile) {
            setFeedback({ type: 'error', message: 'A UI profile must be selected.' });
            return;
        }

        setIsLoading(true);
        setFeedback(null);

        try {
            const configToSave: PathConfigurationRequest = {
                base_path: basePath,
                profile: selectedProfile,
                custom_model_type_paths: modelPaths as Record<string, string>,
                color_theme: currentGlobalTheme,
                config_mode: configMode,
            };

            const response = await configurePathsAPI(configToSave);

            if (response.success && response.current_config) {
                const newConfig = response.current_config;
                setFeedback({
                    type: 'success',
                    message: response.message || 'Configuration saved successfully!',
                });

                // Propagate the newly saved configuration up to the main App component.
                onConfigurationSave(
                    {
                        basePath: newConfig.base_path,
                        uiProfile: newConfig.profile,
                        customPaths: newConfig.custom_model_type_paths || {},
                        configMode: newConfig.config_mode || 'automatic',
                    },
                    newConfig.color_theme || currentGlobalTheme,
                );
            } else {
                throw new Error(response.error || 'Failed to save configuration.');
            }
        } catch (err: any) {
            setFeedback({
                type: 'error',
                message: err.message || 'An unknown API error occurred.',
            });
        } finally {
            setIsLoading(false);
            // Automatically clear feedback message after a few seconds
            setTimeout(() => setFeedback(null), 5000);
        }
    }, [
        basePath,
        selectedProfile,
        modelPaths,
        currentGlobalTheme,
        configMode,
        onConfigurationSave,
    ]);

    // --- Render Logic ---

    return (
        <div className="configurations-page">
            {/* Page Header */}
            <div className="config-header">
                <div className="config-header-text">
                    <h1>Settings</h1>
                    <p>Configure model storage and UI integrations.</p>
                </div>
                <div className="config-mode-switcher" ref={modeSwitcherRef}>
                    <div className="mode-switch-highlight" ref={highlightRef}></div>
                    <div
                        onClick={() => handleModeChange('automatic')}
                        className={`mode-switch-option ${
                            configMode === 'automatic' ? 'active' : ''
                        }`}
                        role="button"
                    >
                        <PackageCheck size={16} /> Automatic
                    </div>
                    <div
                        onClick={() => handleModeChange('manual')}
                        className={`mode-switch-option ${configMode === 'manual' ? 'active' : ''}`}
                        role="button"
                    >
                        <SlidersHorizontal size={16} /> Manual
                    </div>
                </div>
            </div>

            {/* Main Content (Scrollable) */}
            <div className="config-main-content">
                {/* Step 1: Base Path Selection */}
                <div className="config-card">
                    <h2 className="config-card-header">
                        <Folder size={20} />
                        Step 1: Base Storage Location
                    </h2>
                    <div className="config-card-body">
                        <section className="config-section">
                            <label htmlFor="basePathDisplay" className="config-label">
                                Select the main folder where your UIs and models are stored.
                            </label>
                            <div className="base-path-selector">
                                <input
                                    type="text"
                                    id="basePathDisplay"
                                    value={basePath || 'Click "Browse" to select a folder...'}
                                    readOnly
                                    className="config-input path-input"
                                    onClick={() => setIsFolderSelectorOpen(true)}
                                    title={basePath || 'Click to select base folder'}
                                />
                                <button
                                    onClick={() => setIsFolderSelectorOpen(true)}
                                    className="button"
                                >
                                    Browse...
                                </button>
                            </div>
                            {!basePath && (
                                <p className="config-hint error-hint">
                                    This step is required to continue.
                                </p>
                            )}
                        </section>
                    </div>
                </div>

                {/* Step 2: Profile Selection */}
                <div className={`config-card ${!basePath ? 'disabled-card' : ''}`}>
                    <h2 className="config-card-header">
                        {configMode === 'automatic' ? (
                            <Layers size={20} />
                        ) : (
                            <MousePointerClick size={20} />
                        )}
                        Step 2: Select UI Profile
                    </h2>
                    <div className="config-card-body">
                        {configMode === 'automatic' ? (
                            // Automatic Mode: Select from installed UIs
                            installedUis.length > 0 ? (
                                <div className="profile-selector-grid">
                                    {installedUis.map((ui) => (
                                        <div
                                            key={ui.ui_name}
                                            className={`profile-card ${
                                                selectedProfile === ui.ui_name ? 'selected' : ''
                                            }`}
                                            onClick={() => handleProfileSelect(ui.ui_name)}
                                            tabIndex={0}
                                            role="radio"
                                            aria-checked={selectedProfile === ui.ui_name}
                                        >
                                            <span className="profile-card-icon">
                                                {selectedProfile === ui.ui_name ? (
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
                                        No managed UIs found. Install a UI from the 'UI Management'
                                        tab, or switch to <strong>Manual</strong> mode to configure
                                        an existing installation.
                                    </span>
                                </div>
                            )
                        ) : (
                            // Manual Mode: Select from a dropdown
                            <section className="config-section">
                                <label htmlFor="uiProfileSelect" className="config-label">
                                    Choose the profile that matches your UI for the best path
                                    suggestions.
                                </label>
                                <select
                                    id="uiProfileSelect"
                                    value={selectedProfile || ''}
                                    onChange={(e) =>
                                        handleProfileSelect(e.target.value as UiProfileType)
                                    }
                                    className="config-select"
                                >
                                    <option value="" disabled>
                                        Select a profile type...
                                    </option>
                                    <option value="ComfyUI">ComfyUI</option>
                                    <option value="A1111">A1111 / Forge / SD.Next</option>
                                    <option value="Custom">Custom (Advanced)</option>
                                </select>
                            </section>
                        )}
                    </div>
                </div>

                {/* Step 3: Advanced Path Configuration */}
                <div className={`config-card ${!selectedProfile ? 'disabled-card' : ''}`}>
                    <h2 className="config-card-header">
                        <Settings size={20} />
                        Step 3: Fine-Tune Model Paths
                    </h2>
                    <div className="config-card-body">
                        <p className="config-hint">
                            These paths are relative to your base folder:{' '}
                            <code>{basePath || '...'}</code>. Adjust them if your folder structure
                            is different from the default.
                        </p>
                        <div className="custom-paths-list">
                            {modelTypesForPaths.map((mType) => (
                                <div key={mType} className="custom-path-entry">
                                    <label
                                        htmlFor={`modelPath-${mType}`}
                                        className="custom-path-label"
                                    >
                                        {mType}
                                    </label>
                                    <input
                                        type="text"
                                        id={`modelPath-${mType}`}
                                        value={modelPaths[mType] || ''}
                                        placeholder={`e.g., models/${mType}`}
                                        onChange={(e) =>
                                            handleModelPathChange(mType, e.target.value)
                                        }
                                        className="config-input"
                                    />
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>

            {/* Page Footer */}
            <div className="config-footer">
                {feedback && (
                    <div className={`feedback-message ${feedback.type}`}>
                        <AlertTriangle size={16} />
                        <span>{feedback.message}</span>
                    </div>
                )}
                <button
                    onClick={handleSaveConfiguration}
                    disabled={isLoading || !basePath || !selectedProfile}
                    className="button button-primary save-config-button"
                >
                    {isLoading ? <Save size={18} className="animate-spin" /> : <Save size={18} />}
                    {isLoading ? 'Saving...' : 'Save Configuration'}
                </button>
            </div>

            {/* Folder Selector Modal */}
            <FolderSelector
                isOpen={isFolderSelectorOpen}
                onSelectFinalPath={(path) => {
                    setBasePath(path);
                    setIsFolderSelectorOpen(false);
                    // When a new base path is selected, reset the profile to force re-selection
                    handleProfileSelect(null);
                }}
                onCancel={() => setIsFolderSelectorOpen(false)}
            />
        </div>
    );
};

export default ConfigurationsPage;

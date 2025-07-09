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
    type UiNameType,
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
    managedUis: (ManagedUiStatus & { default_profile_name?: UiProfileType })[];
}

/**
 * A comprehensive settings page for configuring the application's core functionalities,
 * including file paths and UI integration modes.
 */
const ConfigurationsPage: React.FC<ConfigurationsPageProps> = ({
    initialPathConfig,
    onConfigurationSave,
    currentGlobalTheme,
    managedUis,
}) => {
    // --- Component State ---
    const [configMode, setConfigMode] = useState<ConfigurationMode>('automatic');
    const [manualBasePath, setManualBasePath] = useState<string | null>(null);
    const [selectedProfile, setSelectedProfile] = useState<UiProfileType | null>(null);
    const [selectedManagedUi, setSelectedManagedUi] = useState<UiNameType | null>(null);
    const [modelPaths, setModelPaths] = useState<Partial<Record<ModelType, string>>>({});
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
        const { configMode, basePath, uiProfile, customPaths, automaticModeUi } = initialPathConfig;
        setConfigMode(configMode || 'automatic');
        setSelectedProfile(uiProfile || null);
        setModelPaths(customPaths || {});
        setSelectedManagedUi(automaticModeUi || null);

        // In manual mode, the basePath from config is the one to use.
        // In automatic mode, it's derived, so we only set the manual path state.
        if (configMode === 'manual') {
            setManualBasePath(basePath || null);
        } else {
            setManualBasePath(null); // Ensure manual path is clear in auto mode
        }
    }, [initialPathConfig]);

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

    const installedUis = useMemo(() => managedUis.filter((ui) => ui.is_installed), [managedUis]);

    const effectiveBasePath = useMemo(() => {
        if (configMode === 'automatic') {
            const ui = installedUis.find((u) => u.ui_name === selectedManagedUi);
            return ui?.install_path || null;
        }
        return manualBasePath;
    }, [configMode, selectedManagedUi, manualBasePath, installedUis]);

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

    const setProfileAndSuggestPaths = useCallback((profile: UiProfileType | null) => {
        setSelectedProfile(profile);
        if (profile && profile !== 'Custom') {
            const defaultPaths = KNOWN_UI_PROFILES[profile] || {};
            setModelPaths(defaultPaths);
        } else if (profile === 'Custom') {
            setModelPaths({}); // Clear paths for custom to avoid carrying over old settings
        }
    }, []);

    const handleManagedUiSelect = useCallback(
        (ui: ManagedUiStatus & { default_profile_name?: UiProfileType }) => {
            setSelectedManagedUi(ui.ui_name);
            setProfileAndSuggestPaths(ui.default_profile_name || 'Custom');
        },
        [setProfileAndSuggestPaths],
    );

    const handleManualProfileSelect = useCallback(
        (profile: UiProfileType | null) => {
            setProfileAndSuggestPaths(profile);
        },
        [setProfileAndSuggestPaths],
    );

    const handleModelPathChange = useCallback((modelType: ModelType, value: string) => {
        setModelPaths((prev) => ({ ...prev, [modelType]: value.trim() }));
    }, []);

    const handleModeChange = (mode: ConfigurationMode) => {
        setConfigMode(mode);
        // Reset selections when switching modes to prevent invalid states
        setSelectedManagedUi(null);
        setManualBasePath(null);
        setProfileAndSuggestPaths(null);
    };

    const handleSaveConfiguration = useCallback(async () => {
        const isAutomaticModeValid = configMode === 'automatic' && selectedManagedUi;
        const isManualModeValid = configMode === 'manual' && manualBasePath;

        if (!isAutomaticModeValid && !isManualModeValid) {
            setFeedback({
                type: 'error',
                message: 'A selection is required for the current mode.',
            });
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
                config_mode: configMode,
                base_path: configMode === 'manual' ? manualBasePath : null,
                automatic_mode_ui: configMode === 'automatic' ? selectedManagedUi : null,
                profile: selectedProfile,
                custom_model_type_paths: modelPaths as Record<string, string>,
                color_theme: currentGlobalTheme,
            };

            const response = await configurePathsAPI(configToSave);

            if (response.success && response.current_config) {
                const newConfig = response.current_config;
                setFeedback({
                    type: 'success',
                    message: response.message || 'Configuration saved successfully!',
                });

                onConfigurationSave(
                    {
                        basePath: newConfig.base_path,
                        uiProfile: newConfig.profile,
                        customPaths: newConfig.custom_model_type_paths || {},
                        configMode: newConfig.config_mode || 'automatic',
                        automaticModeUi: newConfig.automatic_mode_ui || null,
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
            setTimeout(() => setFeedback(null), 5000);
        }
    }, [
        configMode,
        manualBasePath,
        selectedManagedUi,
        selectedProfile,
        modelPaths,
        currentGlobalTheme,
        onConfigurationSave,
    ]);

    // --- Render Logic ---

    const isSaveDisabled =
        isLoading ||
        !selectedProfile ||
        (configMode === 'manual' && !manualBasePath) ||
        (configMode === 'automatic' && !selectedManagedUi);

    return (
        <div className="configurations-page">
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

            <div className="config-main-content">
                {/* Step 1 & 2 combined for clarity */}
                <div className="config-card">
                    <h2 className="config-card-header">
                        {configMode === 'automatic' ? <Layers size={20} /> : <Folder size={20} />}
                        Step 1: Select Configuration Source
                    </h2>
                    <div className="config-card-body">
                        {configMode === 'automatic' ? (
                            <>
                                <label className="config-label">
                                    Select a M.A.L.-managed UI. Its folder will be automatically
                                    used as the base path.
                                </label>
                                {installedUis.length > 0 ? (
                                    <div className="profile-selector-grid">
                                        {installedUis.map((ui) => (
                                            <div
                                                key={ui.ui_name}
                                                className={`profile-card ${
                                                    selectedManagedUi === ui.ui_name
                                                        ? 'selected'
                                                        : ''
                                                }`}
                                                onClick={() => handleManagedUiSelect(ui)}
                                                tabIndex={0}
                                                role="radio"
                                                aria-checked={selectedManagedUi === ui.ui_name}
                                            >
                                                <span className="profile-card-icon">
                                                    {selectedManagedUi === ui.ui_name ? (
                                                        <CheckCircle size={32} />
                                                    ) : (
                                                        <Layers size={32} />
                                                    )}
                                                </span>
                                                <span className="profile-card-name">
                                                    {ui.ui_name}
                                                </span>
                                                <span className="profile-card-tag">Managed</span>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <div className="info-box">
                                        <Info size={24} className="icon" />
                                        <span>
                                            No managed UIs found. Install one from the
                                            'Environments' tab, or switch to <strong>Manual</strong>{' '}
                                            mode.
                                        </span>
                                    </div>
                                )}
                            </>
                        ) : (
                            <section className="config-section">
                                <label htmlFor="basePathDisplay" className="config-label">
                                    Select the main folder where your models are stored.
                                </label>
                                <div className="base-path-selector">
                                    <input
                                        type="text"
                                        id="basePathDisplay"
                                        value={
                                            manualBasePath || 'Click "Browse" to select a folder...'
                                        }
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
                        )}
                    </div>
                </div>

                <div className={`config-card ${!effectiveBasePath ? 'disabled-card' : ''}`}>
                    <h2 className="config-card-header">
                        <MousePointerClick size={20} />
                        Step 2: Select UI Profile
                    </h2>
                    <div className="config-card-body">
                        <section className="config-section">
                            <label htmlFor="uiProfileSelect" className="config-label">
                                Choose the profile that matches your UI's folder structure for the
                                best path suggestions.
                            </label>
                            <select
                                id="uiProfileSelect"
                                value={selectedProfile || ''}
                                onChange={(e) =>
                                    handleManualProfileSelect(e.target.value as UiProfileType)
                                }
                                className="config-select"
                                disabled={configMode === 'automatic'}
                            >
                                <option value="" disabled>
                                    Select a profile type...
                                </option>
                                <option value="ComfyUI">ComfyUI</option>
                                <option value="A1111">A1111 / Forge</option>
                                <option value="Custom">Custom (Advanced)</option>
                            </select>
                            {configMode === 'automatic' && (
                                <p className="config-hint info-hint">
                                    Profile is selected automatically based on your chosen managed
                                    UI.
                                </p>
                            )}
                        </section>
                    </div>
                </div>

                <div className={`config-card ${!selectedProfile ? 'disabled-card' : ''}`}>
                    <h2 className="config-card-header">
                        <Settings size={20} />
                        Step 3: Fine-Tune Model Paths
                    </h2>
                    <div className="config-card-body">
                        <p className="config-hint">
                            These paths are relative to your base folder:{' '}
                            <code>{effectiveBasePath || '...'}</code>
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

            <div className="config-footer">
                {feedback && (
                    <div className={`feedback-message ${feedback.type}`}>
                        <AlertTriangle size={16} />
                        <span>{feedback.message}</span>
                    </div>
                )}
                <button
                    onClick={handleSaveConfiguration}
                    disabled={isSaveDisabled}
                    className="button button-primary save-config-button"
                >
                    {isLoading ? <Save size={18} className="animate-spin" /> : <Save size={18} />}
                    {isLoading ? 'Saving...' : 'Save Configuration'}
                </button>
            </div>

            <FolderSelector
                isOpen={isFolderSelectorOpen}
                onSelectFinalPath={(path) => {
                    setManualBasePath(path);
                    setIsFolderSelectorOpen(false);
                    // When a new base path is selected, reset the profile to force re-selection
                    handleManualProfileSelect(null);
                }}
                onCancel={() => setIsFolderSelectorOpen(false)}
            />
        </div>
    );
};

export default ConfigurationsPage;

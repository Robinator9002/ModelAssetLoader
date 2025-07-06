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
} from 'lucide-react';
import './UiProfileSelector.css';
import './ConfigModeSwitcher.css';

// This is a frontend copy of the backend's KNOWN_UI_PROFILES for instant feedback
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

interface ConfigurationsPageProps {
    initialPathConfig: AppPathConfig; // No longer null due to App.tsx change
    onConfigurationSave: (savedConfig: AppPathConfig, savedTheme: ColorThemeType) => void;
    currentGlobalTheme: ColorThemeType;
    uiStatuses: ManagedUiStatus[];
    initialConfigMode: ConfigurationMode;
}

const ConfigurationsPage: React.FC<ConfigurationsPageProps> = ({
    initialPathConfig,
    onConfigurationSave,
    currentGlobalTheme,
    uiStatuses,
    initialConfigMode,
}) => {
    const [configMode, setConfigMode] = useState<ConfigurationMode>(initialConfigMode);
    const [basePath, setBasePath] = useState<string | null>(null);
    const [selectedProfile, setSelectedProfile] = useState<UiProfileType | null>(null);
    const [modelPaths, setModelPaths] = useState<Partial<Record<ModelType, string>>>({});
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(
        null,
    );
    const [isFolderSelectorOpen, setIsFolderSelectorOpen] = useState(false);

    const modeSwitcherRef = useRef<HTMLDivElement>(null);
    const highlightRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (initialPathConfig) {
            setBasePath(initialPathConfig.basePath || null);
            setSelectedProfile(initialPathConfig.uiProfile || null);
            setModelPaths(initialPathConfig.customPaths || {});
        }
        setConfigMode(initialConfigMode);
    }, [initialPathConfig, initialConfigMode]);

    useEffect(() => {
        if (modeSwitcherRef.current && highlightRef.current) {
            const activeOption = modeSwitcherRef.current.querySelector(
                '.mode-switch-option.active',
            ) as HTMLElement;
            if (activeOption) {
                highlightRef.current.style.left = `${activeOption.offsetLeft}px`;
                highlightRef.current.style.width = `${activeOption.offsetWidth}px`;
            }
        }
    }, [configMode]);

    const handleProfileSelect = useCallback(
        (profile: UiProfileType) => {
            setSelectedProfile(profile);
            if (configMode === 'automatic' && profile !== 'Custom') {
                const defaultPaths = KNOWN_UI_PROFILES[profile] || {};
                setModelPaths(defaultPaths);
            }
        },
        [configMode],
    );

    const handleModelPathChange = useCallback((modelType: ModelType, value: string) => {
        setModelPaths((prev) => ({ ...prev, [modelType]: value.trim() }));
    }, []);

    const handleSaveConfiguration = useCallback(async () => {
        if (!basePath) {
            setFeedback({ type: 'error', message: 'Please select a base path first.' });
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

                // --- FIX IS HERE ---
                // The object passed to onConfigurationSave must match the AppPathConfig interface.
                onConfigurationSave(
                    {
                        basePath: newConfig.base_path,
                        uiProfile: newConfig.profile,
                        customPaths: newConfig.custom_model_type_paths || {},
                        // This property was missing, causing the TypeScript error.
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
        }
    }, [
        basePath,
        selectedProfile,
        modelPaths,
        currentGlobalTheme,
        configMode,
        onConfigurationSave,
    ]);

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

    const renderAutomaticMode = () => (
        <>
            <div className="config-card">
                <h2 className="config-card-header">
                    <Layers size={20} />
                    Managed UI Profile
                </h2>
                <div className="config-card-body">
                    {installedUis.length > 0 ? (
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
                                        <Layers size={24} />
                                    </span>
                                    <span className="profile-card-name">{ui.ui_name}</span>
                                    <span className="profile-card-tag">Managed</span>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="feedback-message warning">
                            <Info size={16} />
                            <span>
                                No managed UIs found. Install a UI from the Environments tab or
                                switch to Manual mode.
                            </span>
                        </div>
                    )}
                </div>
            </div>
            <div className={`config-card custom-paths-card ${selectedProfile ? 'visible' : ''}`}>
                <h2 className="config-card-header">
                    <Folder size={20} />
                    Model Folder Paths
                </h2>
                <div className="config-card-body custom-paths-body">
                    <p className="config-hint">
                        Paths are relative to your base folder: <code>{basePath}</code>
                    </p>
                    <div className="custom-paths-list">
                        {modelTypesForPaths.map((mType) => (
                            <div key={mType} className="custom-path-entry">
                                <label htmlFor={`modelPath-${mType}`} className="custom-path-label">
                                    {mType}
                                </label>
                                <input
                                    type="text"
                                    id={`modelPath-${mType}`}
                                    value={modelPaths[mType] || ''}
                                    placeholder={`e.g., models/${mType}`}
                                    onChange={(e) => handleModelPathChange(mType, e.target.value)}
                                    className="config-input"
                                />
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </>
    );

    const renderManualMode = () => (
        <>
            <div className="config-card">
                <h2 className="config-card-header">
                    <SlidersHorizontal size={20} />
                    Manual Profile
                </h2>
                <div className="config-card-body">
                    <section className="config-section">
                        <label htmlFor="uiProfileSelect" className="config-label">
                            UI Profile (for relative paths)
                        </label>
                        <select
                            id="uiProfileSelect"
                            value={selectedProfile || ''}
                            onChange={(e) => handleProfileSelect(e.target.value as UiProfileType)}
                            className="config-select"
                            disabled={!basePath}
                        >
                            <option value="" disabled>
                                Select a profile...
                            </option>
                            <option value="ComfyUI">ComfyUI</option>
                            <option value="A1111">Automatic1111 / SD.Next / Forge</option>
                            <option value="Custom">Custom</option>
                        </select>
                    </section>
                </div>
            </div>
            <div
                className={`config-card custom-paths-card ${
                    selectedProfile === 'Custom' ? 'visible' : ''
                }`}
            >
                <h2 className="config-card-header">
                    <Settings size={20} />
                    Advanced: Custom Paths
                </h2>
                <div className="config-card-body custom-paths-body">
                    <p className="config-hint">
                        Paths are relative to your base folder: <code>{basePath}</code>
                    </p>
                    <div className="custom-paths-list">
                        {modelTypesForPaths.map((mType) => (
                            <div key={mType} className="custom-path-entry">
                                <label
                                    htmlFor={`customPath-${mType}`}
                                    className="custom-path-label"
                                >
                                    {mType}
                                </label>
                                <input
                                    type="text"
                                    id={`customPath-${mType}`}
                                    value={modelPaths[mType] || ''}
                                    placeholder={`e.g., models/${mType}`}
                                    onChange={(e) => handleModelPathChange(mType, e.target.value)}
                                    className="config-input"
                                />
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </>
    );

    return (
        <div className="configurations-page">
            <div className="config-header">
                <h1>Settings</h1>
                <div className="config-mode-switcher" ref={modeSwitcherRef}>
                    <div className="mode-switch-highlight" ref={highlightRef}></div>
                    <div
                        onClick={() => setConfigMode('automatic')}
                        className={`mode-switch-option ${
                            configMode === 'automatic' ? 'active' : ''
                        }`}
                    >
                        <Layers size={16} /> Automatic
                    </div>
                    <div
                        onClick={() => setConfigMode('manual')}
                        className={`mode-switch-option ${configMode === 'manual' ? 'active' : ''}`}
                    >
                        <SlidersHorizontal size={16} /> Manual
                    </div>
                </div>
            </div>
            <div className="config-main-content">
                <div className="config-card">
                    <h2 className="config-card-header">
                        <Folder size={20} />
                        Base Storage Location
                    </h2>
                    <div className="config-card-body">
                        <section className="config-section">
                            <label htmlFor="basePathDisplay" className="config-label">
                                Base Folder for Models & UIs
                            </label>
                            <div className="base-path-selector">
                                <input
                                    type="text"
                                    id="basePathDisplay"
                                    value={basePath || 'Not set'}
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
                                    A base folder must be selected to continue.
                                </p>
                            )}
                        </section>
                    </div>
                </div>
                {configMode === 'automatic' ? renderAutomaticMode() : renderManualMode()}
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
                    disabled={isLoading || !basePath}
                    className="button button-primary save-config-button"
                >
                    <Save size={18} />
                    {isLoading ? 'Saving...' : 'Save Configuration'}
                </button>
            </div>
            <FolderSelector
                isOpen={isFolderSelectorOpen}
                onSelectFinalPath={(p) => {
                    setBasePath(p);
                    setIsFolderSelectorOpen(false);
                }}
                onCancel={() => setIsFolderSelectorOpen(false)}
            />
        </div>
    );
};

export default ConfigurationsPage;

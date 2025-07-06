// frontend/src/components/Files/ConfigurationsPage.tsx
import React, { useState, useEffect, useCallback } from 'react';
import {
    configurePathsAPI,
    type PathConfigurationRequest,
    type UiProfileType,
    type ModelType,
    type ColorThemeType,
    type ManagedUiStatus, // Import the status type
} from '../../api/api';
import type { AppPathConfig } from '../../App';
import FolderSelector from './FolderSelector';
import { Folder, Settings, Save, AlertTriangle, Layers, Cog } from 'lucide-react';

interface ConfigurationsPageProps {
    initialPathConfig: AppPathConfig | null;
    onConfigurationSave: (savedConfig: AppPathConfig, savedTheme: ColorThemeType) => void;
    currentGlobalTheme: ColorThemeType;
    // Add the list of UI statuses to the props
    uiStatuses: ManagedUiStatus[];
}

const ConfigurationsPage: React.FC<ConfigurationsPageProps> = ({
    initialPathConfig,
    onConfigurationSave,
    currentGlobalTheme,
    uiStatuses, // Destructure the new prop
}) => {
    const [basePath, setBasePath] = useState<string | null>(null);
    const [selectedProfile, setSelectedProfile] = useState<UiProfileType>('ComfyUI');
    const [customPaths, setCustomPaths] = useState<Partial<Record<ModelType, string>>>({});
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(
        null,
    );
    const [isFolderSelectorOpen, setIsFolderSelectorOpen] = useState(false);

    useEffect(() => {
        if (initialPathConfig) {
            setBasePath(initialPathConfig.basePath || null);
            setSelectedProfile(initialPathConfig.uiProfile || 'ComfyUI');
            setCustomPaths(initialPathConfig.customPaths || {});
        }
    }, [initialPathConfig]);

    const handleSelectBasePathClick = useCallback(() => {
        setIsFolderSelectorOpen(true);
    }, []);

    const handleFolderSelected = useCallback((selectedPath: string) => {
        setBasePath(selectedPath);
        setIsFolderSelectorOpen(false);
        setFeedback(null);
    }, []);

    const handleProfileChange = useCallback((profile: UiProfileType) => {
        setSelectedProfile(profile);
    }, []);

    const handleCustomPathChange = useCallback((modelType: ModelType, value: string) => {
        setCustomPaths((prev) => ({ ...prev, [modelType]: value.trim() }));
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
                custom_model_type_paths:
                    selectedProfile === 'Custom' ? (customPaths as Record<string, string>) : {},
                color_theme: currentGlobalTheme,
            };
            const response = await configurePathsAPI(configToSave);
            if (response.success && response.current_config) {
                const newConfig = response.current_config;
                setFeedback({
                    type: 'success',
                    message: response.message || 'Configuration saved successfully!',
                });

                setBasePath(newConfig.base_path || null);
                setSelectedProfile(newConfig.profile || 'ComfyUI');
                setCustomPaths(newConfig.custom_model_type_paths || {});

                onConfigurationSave(
                    {
                        basePath: newConfig.base_path,
                        uiProfile: newConfig.profile,
                        customPaths: newConfig.custom_model_type_paths || {},
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
    }, [basePath, selectedProfile, customPaths, currentGlobalTheme, onConfigurationSave]);

    // Filter for only installed UIs to offer them as profile options
    const installedUis = uiStatuses.filter(status => status.is_installed);

    const modelTypesForCustomPaths: ModelType[] = [
        'checkpoints',
        'loras',
        'vae',
        'embeddings',
        'controlnet',
        'diffusers',
        'clip',
        'unet',
        'hypernetworks',
    ].sort() as ModelType[];

    return (
        <div className="configurations-page">
            <div className="config-header">
                <h1>Settings</h1>
                <p>Configure storage locations and application behavior.</p>
            </div>

            <div className="config-main-content">
                <div className="config-card">
                    <h2 className="config-card-header">
                        <Folder size={20} />
                        Storage & Profiles
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
                                    onClick={handleSelectBasePathClick}
                                    title={basePath || 'Click to select base folder'}
                                />
                                <button onClick={handleSelectBasePathClick} className="button">
                                    Browse...
                                </button>
                            </div>
                            {!basePath && (
                                <p className="config-hint error-hint">
                                    A base folder must be selected to continue.
                                </p>
                            )}
                        </section>

                        <section className="config-section">
                            <label className="config-label">
                                Active UI Profile
                            </label>
                            <div className="profile-selector-container">
                               <div className="profile-selector-grid">
                                    {installedUis.map(ui => (
                                        <div 
                                            key={ui.ui_name}
                                            className={`profile-card ${selectedProfile === ui.ui_name ? 'selected' : ''}`}
                                            onClick={() => handleProfileChange(ui.ui_name)}
                                            tabIndex={0}
                                            role="radio"
                                            aria-checked={selectedProfile === ui.ui_name}
                                        >
                                            <span className="profile-card-icon"><Layers size={24}/></span>
                                            <span className="profile-card-name">{ui.ui_name}</span>
                                            <span className="profile-card-tag">Managed</span>
                                        </div>
                                    ))}
                                    <div 
                                        className={`profile-card ${selectedProfile === 'Custom' ? 'selected' : ''}`}
                                        onClick={() => handleProfileChange('Custom')}
                                        tabIndex={0}
                                        role="radio"
                                        aria-checked={selectedProfile === 'Custom'}
                                    >
                                        <span className="profile-card-icon"><Cog size={24}/></span>
                                        <span className="profile-card-name">Custom</span>
                                    </div>
                               </div>
                               {!basePath && (
                                    <p className="config-hint">Select a base folder to enable profiles.</p>
                                )}
                            </div>
                        </section>
                    </div>
                </div>

                <div
                    className={`config-card custom-paths-card ${
                        selectedProfile === 'Custom' && basePath ? 'visible' : ''
                    }`}
                >
                    <h2 className="config-card-header">
                        <Settings size={20} />
                        Advanced: Custom Paths
                    </h2>
                    <div className="config-card-body custom-paths-body">
                        <p className="config-hint">
                            Define paths relative to your base folder: <code>{basePath}</code>
                        </p>
                        <div className="custom-paths-list">
                            {modelTypesForCustomPaths.map((mType) => (
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
                                        value={customPaths[mType] || ''}
                                        placeholder={`e.g., models/${mType}`}
                                        onChange={(e) =>
                                            handleCustomPathChange(mType, e.target.value)
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
                    disabled={isLoading || !basePath}
                    className="button button-primary save-config-button"
                    title={!basePath ? 'Please select a base folder first' : 'Save configuration'}
                >
                    <Save size={18} />
                    {isLoading ? 'Saving...' : 'Save Configuration'}
                </button>
            </div>

            <FolderSelector
                isOpen={isFolderSelectorOpen}
                onSelectFinalPath={handleFolderSelected}
                onCancel={() => setIsFolderSelectorOpen(false)}
            />
        </div>
    );
};

export default ConfigurationsPage;

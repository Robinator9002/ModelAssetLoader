// frontend/src/components/Files/ConfigurationsPage.tsx
import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
    type PathConfigurationRequest,
    type UiProfileType,
    type ModelType,
    type ManagedUiStatus,
    type ConfigurationMode,
} from '~/api';
import { useConfigStore } from '../../state/configStore';
// --- FIX: Import the useUiStore to get access to availableUis ---
import { useUiStore } from '../../state/uiStore';
import AutomaticModeSettings from './AutomaticModeSettings';
import ManualModeSettings from './ManualModeSettings';
import {
    Settings,
    Save,
    AlertTriangle,
    CheckCircle,
    PackageCheck,
    SlidersHorizontal,
    Loader2,
} from 'lucide-react';

interface ConfigurationsPageProps {
    managedUis: ManagedUiStatus[];
}

const ConfigurationsPage: React.FC<ConfigurationsPageProps> = ({ managedUis }) => {
    // --- State from Zustand Store ---
    const {
        pathConfig,
        theme,
        knownUiProfiles,
        updateConfiguration,
        isLoading: isStoreLoading,
    } = useConfigStore();
    // --- FIX: Destructure availableUis from the uiStore ---
    const { availableUis } = useUiStore();

    // --- Local Component State ---
    const [configMode, setConfigMode] = useState<ConfigurationMode>('automatic');
    const [manualBasePath, setManualBasePath] = useState<string | null>(null);
    const [selectedProfile, setSelectedProfile] = useState<UiProfileType | null>(null);
    const [selectedManagedUiId, setSelectedManagedUiId] = useState<string | null>(null);
    const [modelPaths, setModelPaths] = useState<Partial<Record<ModelType, string>>>({});
    const [isSaving, setIsSaving] = useState<boolean>(false);
    const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(
        null,
    );

    // --- Refs for UI Effects ---
    const modeSwitcherRef = useRef<HTMLDivElement>(null);
    const highlightRef = useRef<HTMLDivElement>(null);

    // --- Effects ---
    useEffect(() => {
        const { configMode, basePath, uiProfile, customPaths, automaticModeUi } = pathConfig;
        setConfigMode(configMode || 'automatic');
        setSelectedProfile(uiProfile || null);
        setModelPaths(customPaths || {});
        setSelectedManagedUiId(automaticModeUi || null);
        if (configMode === 'manual') {
            setManualBasePath(basePath || null);
        } else {
            setManualBasePath(null);
        }
    }, [pathConfig]);

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
            const ui = installedUis.find((u) => u.installation_id === selectedManagedUiId);
            return ui?.install_path || null;
        }
        return manualBasePath;
    }, [configMode, selectedManagedUiId, manualBasePath, installedUis]);

    const modelTypesForPaths = useMemo(
        (): ModelType[] =>
            [
                'Checkpoint',
                'LoRA',
                'VAE',
                'TextualInversion',
                'ControlNet',
                'Upscaler',
                'Hypernetwork',
                'LyCORIS',
                'MotionModule',
            ].sort() as ModelType[],
        [],
    );

    // --- Event Handlers ---
    const setProfileAndSuggestPaths = useCallback(
        (profile: UiProfileType | null) => {
            setSelectedProfile(profile);
            if (profile && profile !== 'Custom' && knownUiProfiles[profile]) {
                setModelPaths(knownUiProfiles[profile] || {});
            } else if (profile === 'Custom') {
                setModelPaths({});
            }
        },
        [knownUiProfiles],
    );

    const handleManagedUiSelect = useCallback(
        (ui: ManagedUiStatus) => {
            // --- FIX: The `availableUis` variable is now correctly in scope ---
            const uiDetails = availableUis.find((item) => item.ui_name === ui.ui_name);
            setSelectedManagedUiId(ui.installation_id);
            setProfileAndSuggestPaths(uiDetails?.default_profile_name || 'Custom');
        },
        [setProfileAndSuggestPaths, availableUis],
    );

    const handleModeChange = (mode: ConfigurationMode) => {
        setConfigMode(mode);
        setSelectedManagedUiId(null);
        setManualBasePath(null);
        setProfileAndSuggestPaths(null);
    };

    const handleSaveConfiguration = useCallback(async () => {
        const isAutomaticModeValid = configMode === 'automatic' && selectedManagedUiId;
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

        setIsSaving(true);
        setFeedback(null);
        try {
            const configToSave: PathConfigurationRequest = {
                config_mode: configMode,
                base_path: configMode === 'manual' ? manualBasePath : null,
                automatic_mode_ui: configMode === 'automatic' ? selectedManagedUiId : null,
                profile: selectedProfile,
                custom_model_type_paths: modelPaths as Record<string, string>,
                color_theme: theme,
            };
            await updateConfiguration(configToSave);
            setFeedback({ type: 'success', message: 'Configuration saved successfully!' });
        } catch (err: any) {
            setFeedback({
                type: 'error',
                message: err.message || 'An unknown API error occurred.',
            });
        } finally {
            setIsSaving(false);
            setTimeout(() => setFeedback(null), 5000);
        }
    }, [
        configMode,
        manualBasePath,
        selectedManagedUiId,
        selectedProfile,
        modelPaths,
        theme,
        updateConfiguration,
    ]);

    // --- Render Logic ---
    const isSaveDisabled =
        isSaving ||
        isStoreLoading ||
        !selectedProfile ||
        (configMode === 'manual' && !manualBasePath) ||
        (configMode === 'automatic' && !selectedManagedUiId);

    if (isStoreLoading) {
        return (
            <div className="page-state-container">
                <Loader2 size={32} className="animate-spin" />
                <p>Loading settings...</p>
            </div>
        );
    }

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
                {configMode === 'automatic' ? (
                    <div className="config-card">
                        <h2 className="config-card-header">
                            <PackageCheck size={20} />
                            Step 1: Select Managed UI Instance
                        </h2>
                        <div className="config-card-body">
                            <AutomaticModeSettings
                                installedUis={installedUis}
                                selectedManagedUiId={selectedManagedUiId}
                                onSelectUi={handleManagedUiSelect}
                            />
                        </div>
                    </div>
                ) : (
                    <ManualModeSettings
                        manualBasePath={manualBasePath}
                        selectedProfile={selectedProfile}
                        onBasePathChange={setManualBasePath}
                        onProfileChange={setProfileAndSuggestPaths}
                    />
                )}

                {(configMode === 'automatic' && selectedManagedUiId) || configMode === 'manual' ? (
                    <div className={`config-card ${!selectedProfile ? 'disabled-card' : ''}`}>
                        <h2 className="config-card-header">
                            <Settings size={20} />
                            Step 2: Fine-Tune Model Paths
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
                                            placeholder={`e.g., models/${mType.toLowerCase()}`}
                                            onChange={(e) =>
                                                setModelPaths((prev) => ({
                                                    ...prev,
                                                    [mType]: e.target.value.trim(),
                                                }))
                                            }
                                            className="config-input"
                                        />
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                ) : null}
            </div>

            <div className="config-footer">
                {feedback && (
                    <div className={`feedback-message ${feedback.type}`}>
                        {feedback.type === 'success' ? (
                            <CheckCircle size={16} />
                        ) : (
                            <AlertTriangle size={16} />
                        )}
                        <span>{feedback.message}</span>
                    </div>
                )}
                <button
                    onClick={handleSaveConfiguration}
                    disabled={isSaveDisabled}
                    className="button button-primary save-config-button"
                >
                    {isSaving ? <Loader2 size={18} className="animate-spin" /> : <Save size={18} />}
                    {isSaving ? 'Saving...' : 'Save Configuration'}
                </button>
            </div>
        </div>
    );
};

export default ConfigurationsPage;

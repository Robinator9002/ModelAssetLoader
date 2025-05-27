// frontend/src/components/Files/ConfigurationsPage.tsx
import React, { useState, useEffect, useCallback } from "react";
import {
    configurePathsAPI,
    type PathConfigurationRequest,
    type UiProfileType,
    type ModelType,
    type ColorThemeType,
} from "../../api/api";
import type { AppPathConfig } from "../../App";
import FolderSelector from "../Layout/FolderSelector";

const logger = {
    info: (...args: any[]) => console.log("[ConfigPage]", ...args),
    warn: (...args: any[]) => console.warn("[ConfigPage]", ...args),
    error: (...args: any[]) => console.error("[ConfigPage]", ...args),
    debug: (...args: any[]) => console.debug("[ConfigPage:DEBUG]", ...args), // Für detaillierteres Debugging
};

interface ConfigurationsPageProps {
    initialPathConfig: AppPathConfig | null;
    onConfigurationSave: (
        savedConfig: AppPathConfig,
        savedTheme: ColorThemeType
    ) => void;
    currentGlobalTheme: ColorThemeType;
}

const ConfigurationsPage: React.FC<ConfigurationsPageProps> = ({
    initialPathConfig,
    onConfigurationSave,
    currentGlobalTheme,
}) => {
    console.log("[ConfigPage] Component mounted/rendered");
    const [basePath, setBasePath] = useState<string | null>(null);
    const [selectedProfile, setSelectedProfile] =
        useState<UiProfileType>("ComfyUI");
    const [customPaths, setCustomPaths] = useState<
        Partial<Record<ModelType, string>>
    >({});

    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [feedback, setFeedback] = useState<{
        type: "success" | "error";
        message: string;
    } | null>(null);

    const [isFolderSelectorOpen, _setIsFolderSelectorOpen] = useState(false); // Original-Setter umbenannt

    // Wrapper für setIsFolderSelectorOpen für detailliertes Logging
    const setIsFolderSelectorOpen = useCallback(
        (
            value: boolean | ((prevState: boolean) => boolean),
            caller?: string
        ) => {
            logger.debug(
                `setIsFolderSelectorOpen CALLED with value: ${String(
                    value
                )}. Caller: ${caller || "Unknown"}`
            );
            try {
                const stack = new Error().stack;
                logger.debug(
                    `Call stack: ${stack?.split("\n").slice(2, 5).join("\n")}`
                );
            } catch (e) {
                /* ignore if stack trace fails */
            }
            _setIsFolderSelectorOpen(value);
        },
        []
    );

    logger.info(
        "[ConfigPage] Rendering. isFolderSelectorOpen:",
        isFolderSelectorOpen
    );

    useEffect(() => {
        logger.info(
            "[ConfigPage] initialPathConfig effect RUNNING",
            initialPathConfig
        );
        if (initialPathConfig) {
            setBasePath(initialPathConfig.basePath || null);
            setSelectedProfile(initialPathConfig.uiProfile || "ComfyUI");
            setCustomPaths(initialPathConfig.customPaths || {});
        } else {
            setBasePath(null);
            setSelectedProfile("ComfyUI");
            setCustomPaths({});
        }
        return () => {
            logger.info("[ConfigPage] initialPathConfig effect CLEANUP");
        };
    }, [initialPathConfig]);

    const handleSelectBasePathClick = useCallback(() => {
        setIsFolderSelectorOpen(true, "handleSelectBasePathClick");
    }, [setIsFolderSelectorOpen]);

    const handleFolderSelected = useCallback(
        (selectedPath: string) => {
            logger.info("FolderSelector: Pfad ausgewählt:", selectedPath);
            setBasePath(selectedPath);
            setIsFolderSelectorOpen(false, "handleFolderSelected");
            setFeedback(null);
        },
        [setIsFolderSelectorOpen]
    );

    const handleProfileChange = useCallback((profile: UiProfileType) => {
        setSelectedProfile(profile);
    }, []);

    const handleCustomPathChange = useCallback(
        (modelType: ModelType, value: string) => {
            setCustomPaths((prev) => ({ ...prev, [modelType]: value.trim() }));
        },
        []
    );

    const handleSaveConfiguration = useCallback(async () => {
        if (!basePath) {
            setFeedback({
                type: "error",
                message: "Bitte wählen Sie zuerst einen Basispfad aus.",
            });
            return;
        }
        setIsLoading(true);
        setFeedback(null);
        try {
            const configToSave: PathConfigurationRequest = {
                base_path: basePath,
                profile: selectedProfile,
                custom_model_type_paths:
                    selectedProfile === "Custom"
                        ? (customPaths as Record<string, string>)
                        : {},
                color_theme: currentGlobalTheme,
            };
            const response = await configurePathsAPI(configToSave);
            if (response.success && response.current_config) {
                const newSavedFullConfig = response.current_config;
                setFeedback({
                    type: "success",
                    message:
                        response.message ||
                        "Konfiguration erfolgreich gespeichert!",
                });
                setBasePath(newSavedFullConfig.base_path || null);
                setSelectedProfile(newSavedFullConfig.profile || "ComfyUI");
                setCustomPaths(
                    newSavedFullConfig.custom_model_type_paths || {}
                );
                onConfigurationSave(
                    {
                        basePath: newSavedFullConfig.base_path,
                        uiProfile: newSavedFullConfig.profile,
                        customPaths:
                            newSavedFullConfig.custom_model_type_paths || {},
                    },
                    newSavedFullConfig.color_theme || currentGlobalTheme
                );
            } else {
                setFeedback({
                    type: "error",
                    message:
                        response.error ||
                        "Fehler beim Speichern der Konfiguration.",
                });
            }
        } catch (err: any) {
            setFeedback({
                type: "error",
                message:
                    err.message ||
                    "Ein unbekannter API-Fehler ist aufgetreten.",
            });
        } finally {
            setIsLoading(false);
        }
    }, [
        basePath,
        selectedProfile,
        customPaths,
        currentGlobalTheme,
        onConfigurationSave,
    ]);

    const handleCancelFolderSelector = useCallback(() => {
        setIsFolderSelectorOpen(
            false,
            "handleCancelFolderSelector (from onCancel prop)"
        );
    }, [setIsFolderSelectorOpen]);

    const modelTypesForCustomPaths: ModelType[] = [
        "checkpoints",
        "loras",
        "vae",
        "embeddings",
        "controlnet",
        "diffusers",
        "clip",
        "unet",
        "hypernetworks",
    ].sort() as ModelType[];

    return (
        <div className="configurations-page">
            <h2>Speicherorte &amp; UI Profil</h2>
            {/* ... rest of the JSX ... */}
            <section className="config-section">
                <label htmlFor="basePathDisplay" className="config-label">
                    Basisordner für Modelle:
                </label>
                <div className="base-path-selector">
                    <input
                        type="text"
                        id="basePathDisplay"
                        value={basePath || "Nicht festgelegt"}
                        readOnly
                        className="config-input path-input"
                        onClick={handleSelectBasePathClick}
                        style={{ cursor: "pointer" }}
                        title={
                            basePath || "Klicken zum Auswählen des Basisordners"
                        }
                    />
                    <button
                        onClick={handleSelectBasePathClick}
                        className="button browse-button"
                    >
                        Ordner Wählen...
                    </button>
                </div>
                {!basePath && (
                    <p className="config-hint error-hint">
                        Ein Basisordner muss ausgewählt werden...
                    </p>
                )}
            </section>

            <section className="config-section">
                <label htmlFor="uiProfileSelect" className="config-label">
                    UI Profil (für relative Pfade):
                </label>
                <select
                    id="uiProfileSelect"
                    value={selectedProfile || ""}
                    onChange={(e) =>
                        handleProfileChange(e.target.value as UiProfileType)
                    }
                    className="config-select"
                    disabled={!basePath}
                >
                    <option value="" disabled={!!selectedProfile}>
                        Bitte Profil wählen
                    </option>
                    <option value="ComfyUI">ComfyUI</option>
                    <option value="A1111">
                        Automatic1111 / SD.Next / Forge
                    </option>
                    <option value="Custom">Benutzerdefiniert</option>
                </select>
                {!basePath && (
                    <p className="config-hint">
                        Wählen Sie zuerst einen Basisordner.
                    </p>
                )}
            </section>

            {selectedProfile === "Custom" && basePath && (
                <section className="config-section custom-paths-section">
                    <h3>
                        Benutzerdefinierte Pfade (relativ zu:{" "}
                        <code>{basePath}</code>)
                    </h3>
                    {/* ... custom paths mapping ... */}
                    {modelTypesForCustomPaths.map((mType) => (
                        <div key={mType} className="custom-path-entry">
                            <label
                                htmlFor={`customPath-${mType}`}
                                className="custom-path-label"
                            >
                                {mType.charAt(0).toUpperCase() + mType.slice(1)}
                                :
                            </label>
                            <input
                                type="text"
                                id={`customPath-${mType}`}
                                value={customPaths[mType] || ""}
                                placeholder={`z.B. models/${mType}`}
                                onChange={(e) =>
                                    handleCustomPathChange(
                                        mType,
                                        e.target.value
                                    )
                                }
                                className="config-input"
                            />
                        </div>
                    ))}
                </section>
            )}
            <div className="config-actions">
                <button
                    onClick={handleSaveConfiguration}
                    disabled={isLoading || !basePath}
                    className="button save-config-button"
                    title={
                        !basePath
                            ? "Bitte zuerst einen Basisordner auswählen"
                            : "Konfiguration speichern"
                    }
                >
                    {isLoading ? "Speichern..." : "Konfiguration Speichern"}
                </button>
            </div>

            {feedback && (
                <p className={`feedback-message ${feedback.type}`}>
                    {feedback.message}
                </p>
            )}

            <FolderSelector
                key="folder-selector-stable-key" // Behalte den statischen Key!
                isOpen={isFolderSelectorOpen}
                onSelectFinalPath={handleFolderSelected}
                onCancel={handleCancelFolderSelector}
            />
        </div>
    );
};

export default ConfigurationsPage;

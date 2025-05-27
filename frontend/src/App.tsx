// frontend/src/App.tsx
import React, { useState, useEffect, useCallback } from "react";
import "./App.css";
import ThemeSwitcher from "./components/Theme/ThemeSwitcher";
import Navbar, { type MalTabKey } from "./components/Layout/Navbar";
import ModelSearchPage from "./components/ModelLoader/ModelSearchPage";
import ModelDetailsPage from "./components/ModelLoader/ModelDetailsPage";
import ConfigurationsPage from "./components/Files/ConfigurationsPage";
import DownloadModal from "./components/Files/DownloadModal";
import ConfirmModal from "./components/Layout/ConfirmModal";

import {
    getCurrentConfigurationAPI,
    configurePathsAPI,
    type PathConfigurationRequest,
    type ColorThemeType,
    type MalFullConfiguration,
    type HFModelListItem,
    type HFModelDetails,
    type HFModelFile,
} from "./api/api";
import appIcon from "/icon.png";

const logger = {
    info: (...args: any[]) => console.log("[App]", ...args),
    error: (...args: any[]) => console.error("[App]", ...args),
    warn: (...args: any[]) => console.warn("[App]", ...args),
};

export interface AppPathConfig {
    basePath: string | null;
    uiProfile: MalFullConfiguration["profile"];
    customPaths: MalFullConfiguration["custom_model_type_paths"];
}

function App() {
    console.log("[App] Component rendering/re-rendering");
    const [pathConfig, setPathConfig] = useState<AppPathConfig | null>(null);
    const [theme, setTheme] = useState<ColorThemeType>("dark");
    const [activeTab, setActiveTab] = useState<MalTabKey>("search");
    const [selectedModelForDetails, setSelectedModelForDetails] =
        useState<HFModelListItem | null>(null);
    const [isConfigLoading, setIsConfigLoading] = useState<boolean>(true);

    const [isDownloadModalOpen, setIsDownloadModalOpen] =
        useState<boolean>(false);
    const [modelForDownload, setModelForDownload] =
        useState<HFModelDetails | null>(null);
    const [specificFileForDownload, setSpecificFileForDownload] =
        useState<HFModelFile | null>(null);

    const [isConfirmModalOpen, setIsConfirmModalOpen] =
        useState<boolean>(false);
    const [confirmModalProps, setConfirmModalProps] = useState<{
        title?: string;
        message: string | React.ReactNode;
        onConfirm: () => void;
    } | null>(null);

    // const openConfirmModal = useCallback(( // Vorerst auskommentiert, falls nicht direkt benötigt
    // 	message: string | React.ReactNode,
    // 	onConfirm: () => void,
    // 	title?: string
    // ) => {
    // 	setConfirmModalProps({ message, onConfirm, title });
    // 	setIsConfirmModalOpen(true);
    // }, []);

    const closeConfirmModal = useCallback(() => {
        setIsConfirmModalOpen(false);
        setConfirmModalProps(null);
    }, []);

    const openDownloadModal = useCallback(
        (modelDetails: HFModelDetails, specificFile?: HFModelFile) => {
            logger.info(
                "Öffne DownloadModal für:",
                modelDetails.id,
                "Spezifische Datei:",
                specificFile?.rfilename
            );
            setModelForDownload(modelDetails);
            setSpecificFileForDownload(specificFile || null);
            setIsDownloadModalOpen(true);
        },
        []
    );

    const closeDownloadModal = useCallback(() => {
        setIsDownloadModalOpen(false);
        setModelForDownload(null);
        setSpecificFileForDownload(null);
    }, []);

    const loadInitialConfig = useCallback(async () => {
        logger.info("Lade initiale Konfiguration...");
        setIsConfigLoading(true);
        try {
            const configFromBackend = await getCurrentConfigurationAPI();
            logger.info(
                "Konfiguration vom Backend geladen:",
                configFromBackend
            );

            const newPathConfig = {
                basePath: configFromBackend.base_path,
                uiProfile: configFromBackend.profile,
                customPaths: configFromBackend.custom_model_type_paths || {},
            };
            setPathConfig(newPathConfig);
            setTheme(configFromBackend.color_theme || "dark");

            localStorage.setItem(
                "malPathConfig",
                JSON.stringify(newPathConfig)
            );
            localStorage.setItem(
                "malTheme",
                configFromBackend.color_theme || "dark"
            );
        } catch (error) {
            logger.error(
                "Fehler beim Laden der initialen Konfiguration vom Backend:",
                error
            );
            const storedPathConfigRaw = localStorage.getItem("malPathConfig");
            if (storedPathConfigRaw) {
                try {
                    const storedConfig = JSON.parse(
                        storedPathConfigRaw
                    ) as AppPathConfig;
                    setPathConfig(storedConfig);
                } catch (e) {
                    logger.error(
                        "Fehler beim Parsen von localStorage malPathConfig",
                        e
                    );
                    setPathConfig(null);
                }
            } else {
                setPathConfig(null);
            }
            const storedTheme = localStorage.getItem(
                "malTheme"
            ) as ColorThemeType | null;
            setTheme(storedTheme || "dark");
        } finally {
            setIsConfigLoading(false);
        }
    }, []); // Keine Abhängigkeiten, da es nur beim Mount aufgerufen werden soll und keine externen Variablen verwendet, die sich ändern.

    useEffect(() => {
        loadInitialConfig();
    }, [loadInitialConfig]); // loadInitialConfig ist durch useCallback stabil

    useEffect(() => {
        document.body.className = theme === "light" ? "light-theme" : "";
        logger.info(`Theme auf Body gesetzt: ${theme}`);
    }, [theme]);

    const handleThemeToggleAndSave = useCallback(async () => {
        const newTheme = theme === "light" ? "dark" : "light";
        setTheme(newTheme);
        localStorage.setItem("malTheme", newTheme);

        try {
            logger.info(`Speichere neues Theme im Backend: ${newTheme}`);
            const currentPathConfig = pathConfig; // Lokale Kopie für den Request
            const configRequest: PathConfigurationRequest = {
                base_path: currentPathConfig?.basePath || null,
                profile: currentPathConfig?.uiProfile || null,
                custom_model_type_paths: currentPathConfig?.customPaths || {},
                color_theme: newTheme,
            };
            const response = await configurePathsAPI(configRequest);
            if (response.success && response.current_config) {
                logger.info(
                    "Theme erfolgreich im Backend gespeichert. Aktuelle Gesamtkonfig:",
                    response.current_config
                );
                // Backend sendet die volle Konfig zurück, also aktualisieren wir pathConfig
                setPathConfig({
                    basePath: response.current_config.base_path,
                    uiProfile: response.current_config.profile,
                    customPaths:
                        response.current_config.custom_model_type_paths || {},
                });
            } else {
                logger.error(
                    "Fehler beim Speichern des Themes im Backend:",
                    response.error || "Antwort nicht erfolgreich."
                );
                // Optional: Theme zurücksetzen, falls Speichern fehlschlägt
                // Hier könnte man den alten Theme-Wert wiederherstellen
            }
        } catch (error) {
            logger.error(
                "Fehler beim API-Aufruf zum Speichern des Themes:",
                error
            );
        }
    }, [theme, pathConfig]); // pathConfig als Abhängigkeit, da es im Request verwendet wird

    const handleModelSelectForDetails = useCallback(
        (model: HFModelListItem) => {
            setSelectedModelForDetails(model);
        },
        []
    );

    const handleBackToSearch = useCallback(() => {
        setSelectedModelForDetails(null);
    }, []);

    const handlePathConfigurationUpdate = useCallback(
        (updatedConfig: AppPathConfig, updatedTheme?: ColorThemeType) => {
            logger.info(
                "Pfad-Konfiguration in App.tsx aktualisiert:",
                updatedConfig
            );
            setPathConfig(updatedConfig);
            localStorage.setItem(
                "malPathConfig",
                JSON.stringify(updatedConfig)
            );
            if (updatedTheme) {
                setTheme(updatedTheme);
                localStorage.setItem("malTheme", updatedTheme);
            }
        },
        [] // Keine Abhängigkeiten, da es nur Setter aufruft und keine externen Variablen liest, die sich ändern.
    );

    const renderActiveTabContent = () => {
        console.log(
            `[App renderActiveTabContent] isConfigLoading: ${isConfigLoading}, selectedModelForDetails: ${!!selectedModelForDetails}, activeTab: ${activeTab}`
        );
        if (isConfigLoading) {
            return <p className="loading-message">Lade Konfiguration...</p>;
        }

        if (selectedModelForDetails) {
            return (
                <ModelDetailsPage
                    modelId={selectedModelForDetails.id}
                    onBack={handleBackToSearch}
                    openDownloadModal={openDownloadModal}
                />
            );
        }

        switch (activeTab) {
            case "search":
                return (
                    <ModelSearchPage
                        onModelSelect={handleModelSelectForDetails}
                        openDownloadModal={openDownloadModal}
                        isConfigurationDone={!!pathConfig?.basePath}
                    />
                );
            case "configuration":
                return (
                    <ConfigurationsPage
                        // WICHTIG: Key hinzugefügt, um die Komponente bei Bedarf neu zu initialisieren,
                        // aber hier wollen wir Stabilität, solange sie sichtbar ist.
                        // Ein statischer Key ist besser, wenn die Komponente nicht bei jedem Tab-Wechsel
                        // komplett neu gemountet werden soll. Da sie aber nur bei activeTab='configuration'
                        // gerendert wird, ist der Key hier vielleicht nicht das Hauptproblem,
                        // aber ein expliziter Key ist immer gut.
                        key="configurations-page-stable"
                        initialPathConfig={pathConfig}
                        onConfigurationSave={handlePathConfigurationUpdate}
                        currentGlobalTheme={theme}
                    />
                );
            default:
                return (
                    <ModelSearchPage
                        onModelSelect={handleModelSelectForDetails}
                        openDownloadModal={openDownloadModal}
                        isConfigurationDone={!!pathConfig?.basePath}
                    />
                );
        }
    };

    return (
        <div className="app-wrapper">
            <header className="app-header-placeholder">
                <div
                    style={{
                        gap: "1rem",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                    }}
                >
                    <img
                        src={appIcon}
                        style={{ width: "2rem", height: "auto" }}
                        alt="M.A.L. Icon"
                    />
                    <h1>M.A.L.</h1>
                </div>
            </header>

            <Navbar
                activeTab={activeTab}
                onTabChange={(tab) => {
                    setSelectedModelForDetails(null);
                    setActiveTab(tab);
                }}
            />

            <main className="main-content-area">
                {renderActiveTabContent()}
            </main>

            <div className="theme-switcher-container">
                <ThemeSwitcher
                    currentTheme={theme}
                    onToggleTheme={handleThemeToggleAndSave}
                />
            </div>

            <DownloadModal
                isOpen={isDownloadModalOpen}
                onClose={closeDownloadModal}
                modelDetails={modelForDownload}
                specificFileToDownload={specificFileForDownload}
            />

            {isConfirmModalOpen && confirmModalProps && (
                <ConfirmModal
                    isOpen={isConfirmModalOpen}
                    title={confirmModalProps.title}
                    message={confirmModalProps.message}
                    onConfirm={() => {
                        if (confirmModalProps) confirmModalProps.onConfirm(); // Sicherstellen, dass confirmModalProps noch existiert
                        closeConfirmModal();
                    }}
                    onCancel={closeConfirmModal}
                />
            )}
        </div>
    );
}

export default App;

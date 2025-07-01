// frontend/src/App.tsx
import { useState, useEffect, useCallback, useRef } from "react";
import "./App.css";
import Navbar, { type MalTabKey } from "./components/Layout/Navbar";
import ThemeSwitcher from "./components/Theme/ThemeSwitcher";
import ModelSearchPage from "./components/ModelLoader/ModelSearchPage";
import ModelDetailsPage from "./components/ModelLoader/ModelDetailsPage";
import ConfigurationsPage from "./components/Files/ConfigurationsPage";
import DownloadModal from "./components/Downloads/DownloadModal";
import DownloadManager from "./components/Downloads/DownloadManager"; // <-- ADDED

import {
  // API and WebSocket functions
  getCurrentConfigurationAPI,
  configurePathsAPI,
  connectToDownloadTracker, // <-- ADDED
  // Types
  type PathConfigurationRequest,
  type ColorThemeType,
  type MalFullConfiguration,
  type ModelListItem,
  type ModelDetails,
  type ModelFile,
  type DownloadStatus, // <-- ADDED
} from "./api/api";
import appIcon from "/icon.png";

const logger = {
  info: (...args: any[]) => console.log("[App]", ...args),
  error: (...args: any[]) => console.error("[App]", ...args),
};

export interface AppPathConfig {
  basePath: string | null;
  uiProfile: MalFullConfiguration["profile"];
  customPaths: MalFullConfiguration["custom_model_type_paths"];
}

function App() {
  const [pathConfig, setPathConfig] = useState<AppPathConfig | null>(null);
  const [theme, setTheme] = useState<ColorThemeType>("dark");
  const [activeTab, setActiveTab] = useState<MalTabKey>("search");
  const [isConfigLoading, setIsConfigLoading] = useState<boolean>(true);

  // --- State for Views ---
  const [selectedModel, setSelectedModel] = useState<ModelListItem | null>(
    null
  );

  // --- State for Download Modal ---
  const [isDownloadModalOpen, setIsDownloadModalOpen] =
    useState<boolean>(false);
  const [modelForDownload, setModelForDownload] = useState<ModelDetails | null>(
    null
  );
  const [specificFileForDownload, setSpecificFileForDownload] =
    useState<ModelFile | null>(null);

  // --- REFACTOR: State for Download Tracking via WebSocket ---
  const [activeDownloads, setActiveDownloads] = useState<
    Map<string, DownloadStatus>
  >(new Map());

  // REFACTOR: Use a ref to hold the WebSocket instance to prevent re-creation
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    // Only establish connection if it doesn't exist
    if (!ws.current) {
      logger.info("Setting up WebSocket for download tracking...");
      const handleWsMessage = (data: any) => {
        if (data.type === "initial_state") {
          const initialMap = new Map<string, DownloadStatus>();
          if (data.downloads && Array.isArray(data.downloads)) {
            data.downloads.forEach((status: DownloadStatus) => {
              initialMap.set(status.download_id, status);
            });
          }
          setActiveDownloads(initialMap);
          logger.info("Download tracker initial state received:", initialMap);
        } else {
          const status: DownloadStatus = data;
          setActiveDownloads((prev) =>
            new Map(prev).set(status.download_id, status)
          );
        }
      };

      const socket = connectToDownloadTracker(handleWsMessage);
      ws.current = socket;
    }

    // Cleanup function will be called on component unmount
    return () => {
      if (ws.current && ws.current.readyState === WebSocket.OPEN) {
        logger.info("Closing WebSocket connection on cleanup.");
        ws.current.close();
      }
      // In dev-mode with StrictMode, this cleanup runs, so we nullify the ref
      // to allow re-connection on the second mount.
      ws.current = null;
    };
  }, []); // Empty dependency array ensures this runs only once per real mount

  const openDownloadModal = useCallback(
    (modelDetails: ModelDetails, specificFile?: ModelFile) => {
      logger.info(
        "Opening DownloadModal for:",
        modelDetails.id,
        "Specific file:",
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
    setIsConfigLoading(true);
    try {
      const config = await getCurrentConfigurationAPI();
      const newPathConfig = {
        basePath: config.base_path,
        uiProfile: config.profile,
        customPaths: config.custom_model_type_paths || {},
      };
      setPathConfig(newPathConfig);
      setTheme(config.color_theme || "dark");
    } catch (error) {
      logger.error("Failed to load initial config from backend:", error);
      setPathConfig(null);
      setTheme("dark");
    } finally {
      setIsConfigLoading(false);
    }
  }, []);

  useEffect(() => {
    loadInitialConfig();
  }, [loadInitialConfig]);

  useEffect(() => {
    document.body.className = theme === "light" ? "light-theme" : "";
  }, [theme]);

  const handleThemeToggleAndSave = useCallback(async () => {
    const newTheme = theme === "light" ? "dark" : "light";
    setTheme(newTheme);
    try {
      const configRequest: PathConfigurationRequest = {
        ...pathConfig,
        color_theme: newTheme,
        base_path: pathConfig?.basePath || null,
      };
      await configurePathsAPI(configRequest);
    } catch (error) {
      logger.error("Failed to save theme to backend:", error);
    }
  }, [theme, pathConfig]);

  const handleModelSelect = useCallback((model: ModelListItem) => {
    setSelectedModel(model);
  }, []);

  const handleBackToSearch = useCallback(() => {
    setSelectedModel(null);
  }, []);

  const handlePathConfigurationUpdate = useCallback(
    (updatedConfig: AppPathConfig, updatedTheme?: ColorThemeType) => {
      setPathConfig(updatedConfig);
      if (updatedTheme) {
        setTheme(updatedTheme);
      }
    },
    []
  );

  const renderActiveTabContent = () => {
    if (isConfigLoading) {
      return <p className="loading-message">Lade Konfiguration...</p>;
    }

    if (selectedModel) {
      return (
        <ModelDetailsPage
          selectedModel={selectedModel} // REFACTOR: Pass the whole model item
          onBack={handleBackToSearch}
          openDownloadModal={openDownloadModal}
        />
      );
    }

    switch (activeTab) {
      case "search":
        return (
          <ModelSearchPage
            onModelSelect={handleModelSelect}
            openDownloadModal={openDownloadModal}
            isConfigurationDone={!!pathConfig?.basePath}
          />
        );
      case "configuration":
        return (
          <ConfigurationsPage
            initialPathConfig={pathConfig}
            onConfigurationSave={handlePathConfigurationUpdate}
            currentGlobalTheme={theme}
          />
        );
      default:
        return (
          <ModelSearchPage
            onModelSelect={handleModelSelect}
            openDownloadModal={openDownloadModal}
            isConfigurationDone={!!pathConfig?.basePath}
          />
        );
    }
  };

  return (
    <div className="app-wrapper">
      {/* --- ADDED: The global download manager toast container --- */}
      <DownloadManager activeDownloads={activeDownloads} />

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
          setSelectedModel(null); // Always go back to search list on tab change
          setActiveTab(tab);
        }}
      />

      <main className="main-content-area">{renderActiveTabContent()}</main>

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
    </div>
  );
}

export default App;

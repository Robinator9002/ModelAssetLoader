// frontend/src/state/configStore.ts
import { create } from 'zustand';
import {
    // API functions for fetching and saving configuration
    getCurrentConfigurationAPI,
    configurePathsAPI,
    getKnownUiProfilesAPI, // <-- Import the new API function
    // Type definitions from the API layer
    type ColorThemeType,
    type UiProfileType,
    type ConfigurationMode,
    type UiNameType,
    type PathConfigurationRequest,
    type ModelType, // <-- Import ModelType for use in the profile dictionary
} from '~/api';

/**
 * @interface AppPathConfig
 * Defines the core shape of the application's path and UI configuration state.
 * This is used throughout the application to determine where to save models
 * and which UI profile's folder structure to use.
 */
export interface AppPathConfig {
    basePath: string | null;
    uiProfile: UiProfileType | null;
    customPaths: Partial<Record<ModelType, string>>; // Use Partial as not all model types may be defined
    configMode: ConfigurationMode;
    automaticModeUi: UiNameType | null;
}

/**
 * @interface ConfigState
 * Defines the complete shape of the configuration store's state, including
 * the main configuration object, the color theme, loading status, and fetched
 * data like known UI profiles.
 */
interface ConfigState {
    // State properties
    pathConfig: AppPathConfig;
    theme: ColorThemeType;
    isLoading: boolean;
    /**
     * @fix {DATA_INTEGRITY} Added state to hold UI profiles fetched from the backend.
     * This ensures the frontend uses the single source of truth from the server
     * instead of a hardcoded, potentially outdated constant.
     */
    knownUiProfiles: Record<UiProfileType, Partial<Record<ModelType, string>>>;

    // Actions (functions to modify the state)
    loadInitialConfig: () => Promise<void>;
    updateConfiguration: (newConfig: PathConfigurationRequest) => Promise<void>;
    setTheme: (theme: ColorThemeType) => void;
}

/**
 * `useConfigStore` is a custom hook created by Zustand.
 *
 * This store is the single source of truth for all application-level configuration.
 * It encapsulates the state related to paths, UI profiles, and themes, as well as
 * the async actions required to fetch and save that configuration.
 */
export const useConfigStore = create<ConfigState>((set, get) => ({
    // --- INITIAL STATE ---
    pathConfig: {
        basePath: null,
        uiProfile: null,
        customPaths: {},
        configMode: 'automatic',
        automaticModeUi: null,
    },
    theme: 'dark',
    isLoading: true,
    knownUiProfiles: {} as Record<UiProfileType, Partial<Record<ModelType, string>>>, // Starts empty

    // --- ACTIONS ---

    /**
     * Fetches the initial configuration and known UI profiles from the backend.
     * This action is called once when the application first loads.
     */
    loadInitialConfig: async () => {
        set({ isLoading: true });
        try {
            /**
             * @fix {DATA_INTEGRITY} Fetch both config and profiles in parallel.
             * This efficiently loads all necessary startup data and ensures the
             * frontend has the canonical UI profile data from the backend.
             */
            const [config, profiles] = await Promise.all([
                getCurrentConfigurationAPI(),
                getKnownUiProfilesAPI(),
            ]);

            set({
                pathConfig: {
                    basePath: config.base_path,
                    uiProfile: config.profile,
                    customPaths: config.custom_model_type_paths || {},
                    configMode: config.config_mode || 'automatic',
                    automaticModeUi: config.automatic_mode_ui || null,
                },
                theme: config.color_theme || 'dark',
                knownUiProfiles: profiles as Record<
                    UiProfileType,
                    Partial<Record<ModelType, string>>
                >,
            });
        } catch (error) {
            console.error('Failed to load initial application config:', error);
            // In case of an error, we still want to stop the loading state.
        } finally {
            set({ isLoading: false });
        }
    },

    /**
     * Saves a new configuration to the backend and updates the local state on success.
     * @param {PathConfigurationRequest} newConfig - The configuration object to save.
     */
    updateConfiguration: async (newConfig: PathConfigurationRequest) => {
        try {
            const response = await configurePathsAPI(newConfig);
            if (response.success && response.current_config) {
                const updated = response.current_config;
                set({
                    pathConfig: {
                        basePath: updated.base_path,
                        uiProfile: updated.profile,
                        customPaths: updated.custom_model_type_paths || {},
                        configMode: updated.config_mode || 'automatic',
                        automaticModeUi: updated.automatic_mode_ui || null,
                    },
                    theme: updated.color_theme || get().theme,
                });
            } else {
                throw new Error(response.error || 'Failed to save configuration.');
            }
        } catch (error) {
            console.error('Error saving configuration:', error);
            throw error;
        }
    },

    /**
     * Updates the color theme in the state and persists it to the backend.
     * @param {ColorThemeType} newTheme - The new theme to apply ('light' or 'dark').
     */
    setTheme: (newTheme: ColorThemeType) => {
        set({ theme: newTheme });
        // Persist the theme change to the backend without affecting other settings.
        configurePathsAPI({ color_theme: newTheme }).catch((error) => {
            console.error('Failed to save theme to backend:', error);
        });
    },
}));

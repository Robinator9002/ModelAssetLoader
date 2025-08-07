// frontend/src/api/types.ts

/**
 * @file This file centralizes all TypeScript type definitions and interfaces
 * used across the API modules. By consolidating them here, we ensure type
 * consistency and make it easier to manage data structures as the application evolves.
 */

// --- Generic Model Interfaces ---

export interface ModelFile {
    rfilename: string;
    size?: number | null;
}

export interface ModelListItem {
    id: string;
    source: string;
    author?: string | null;
    model_name: string;
    last_modified?: string | null; // ISO Date String
    tags: string[];
    pipeline_tag?: string | null;
    downloads?: number | null;
    likes?: number | null;
}

export interface PaginatedModelListResponse {
    items: ModelListItem[];
    page: number;
    limit: number;
    has_more: boolean;
}

export interface ModelDetails extends ModelListItem {
    sha?: string | null;
    private?: boolean | null;
    gated?: string | null;
    library_name?: string | null;
    siblings: ModelFile[];
    readme_content?: string | null;
}

export interface SearchModelParams {
    source?: string;
    search?: string;
    author?: string;
    tags?: string[];
    sort?: 'lastModified' | 'downloads' | 'likes' | 'author' | 'id';
    direction?: -1 | 1;
    limit?: number;
    page?: number;
}

// --- FileManager & Download Interfaces ---

export type UiNameType = 'ComfyUI' | 'A1111' | 'Forge' | 'Fooocus';
export type UiProfileType = 'ComfyUI' | 'A1111' | 'Forge' | 'Custom';
export type ColorThemeType = 'dark' | 'light';
export type ModelType =
    | 'Checkpoint'
    | 'VAE'
    | 'LoRA'
    | 'LyCORIS'
    | 'ControlNet'
    | 'Upscaler'
    | 'Hypernetwork'
    | 'TextualInversion'
    | 'MotionModule'
    | 'Other';
export type ConfigurationMode = 'automatic' | 'manual';

export interface PathConfigurationRequest {
    base_path?: string | null;
    profile?: UiProfileType | null;
    custom_model_type_paths?: Record<string, string> | null;
    color_theme?: ColorThemeType | null;
    config_mode?: ConfigurationMode | null;
    // --- REFACTOR: This now sends the unique ID of the installation ---
    automatic_mode_ui?: string | null;
}

export interface MalFullConfiguration {
    base_path: string | null;
    profile: UiProfileType | null;
    custom_model_type_paths: Record<string, string>;
    color_theme: ColorThemeType | null;
    config_mode: ConfigurationMode | null;
    // --- REFACTOR: This now holds the unique ID of the installation ---
    automatic_mode_ui: string | null;
}

export interface PathConfigurationResponse {
    success: boolean;
    message?: string | null;
    error?: string | null;
    current_config?: MalFullConfiguration | null;
}

export interface FileDownloadRequest {
    source: string;
    repo_id: string;
    filename: string;
    model_type: ModelType;
    custom_sub_path?: string | null;
    revision?: string | null;
}

export interface FileDownloadResponse {
    success: boolean;
    message?: string | null;
    error?: string | null;
    download_id?: string | null;
}

// --- Download Tracker WebSocket Interface ---

export interface DownloadStatus {
    download_id: string;
    filename: string;
    repo_id: string;
    status: 'pending' | 'downloading' | 'running' | 'completed' | 'error' | 'cancelled';
    progress: number;
    total_size_bytes: number;
    downloaded_bytes: number;
    error_message?: string | null;
    status_text?: string | null;
    target_path?: string | null;
    set_as_active_on_completion?: boolean;
}

// --- Host Directory Scanning Interfaces ---

export interface HostDirectoryItem {
    name: string;
    path: string;
    type: 'directory';
    children?: HostDirectoryItem[] | null;
}

export interface ScanHostDirectoriesResponse {
    success: boolean;
    message?: string | null;
    error?: string | null;
    data?: HostDirectoryItem[] | null;
}

// --- Interfaces for Local File Management ---

export interface LocalFileItem {
    name: string;
    path: string;
    item_type: 'file' | 'directory';
    size: number | null;
    last_modified: string;
}

export interface FilePreviewResponse {
    success: boolean;
    path: string;
    content?: string | null;
    error?: string | null;
}

export interface FileManagerListResponse {
    path: string | null;
    items: LocalFileItem[];
}

export type ViewMode = 'models' | 'explorer';

// --- UI Environment Management Interfaces ---

export interface AvailableUiItem {
    ui_name: UiNameType;
    git_url: string;
    default_profile_name: UiProfileType;
}

export interface UiInstallRequest {
    ui_name: UiNameType;
    // --- NEW: Add a user-provided name for the new instance ---
    display_name: string;
    custom_install_path: string | null;
    set_as_active: boolean;
}

export interface ManagedUiStatus {
    // --- NEW: Add the unique ID and display name for the instance ---
    installation_id: string;
    display_name: string;
    // --- The ui_name now refers to the *type* of UI (e.g., ComfyUI) ---
    ui_name: UiNameType;
    is_installed: boolean;
    is_running: boolean;
    install_path: string | null;
    running_task_id: string | null;
}

export interface AllUiStatusResponse {
    items: ManagedUiStatus[];
}

export interface UiActionResponse {
    success: boolean;
    message: string;
    task_id: string;
    set_as_active_on_completion: boolean;
}

// --- UI Environment Adoption Interfaces ---

export interface AdoptionIssue {
    code: string;
    message: string;
    is_fixable: boolean;
    fix_description: string;
    default_fix_enabled: boolean;
}

export interface AdoptionAnalysisResponse {
    is_adoptable: boolean;
    is_healthy: boolean;
    issues: AdoptionIssue[];
}

export interface UiAdoptionAnalysisRequest {
    ui_name: UiNameType;
    path: string;
}

export interface UiAdoptionRepairRequest {
    // --- NEW: Add display_name for the new instance being adopted ---
    ui_name: UiNameType;
    display_name: string;
    path: string;
    issues_to_fix: string[];
}

export interface UiAdoptionFinalizeRequest {
    // --- NEW: Add display_name for the new instance being adopted ---
    ui_name: UiNameType;
    display_name: string;
    path: string;
}

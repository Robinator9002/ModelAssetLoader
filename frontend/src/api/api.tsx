// frontend/src/api/api.tsx
import axios, { type AxiosInstance } from 'axios';

const API_BASE_URL = 'http://localhost:8000/api';
const WS_BASE_URL = 'ws://localhost:8000';

const apiClient: AxiosInstance = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

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
    lastModified?: string | null; // ISO Date String
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
export type UiNameType = 'ComfyUI' | 'A1111' | 'ForgeUI';
export type UiProfileType = UiNameType | 'Custom';
export type ColorThemeType = 'dark' | 'light';
export type ModelType =
    | 'checkpoints'
    | 'loras'
    | 'vae'
    | 'clip'
    | 'unet'
    | 'controlnet'
    | 'embeddings'
    | 'hypernetworks'
    | 'diffusers'
    | 'custom';
export type ConfigurationMode = 'automatic' | 'manual';

export interface PathConfigurationRequest {
    base_path?: string | null;
    profile?: UiProfileType | null;
    custom_model_type_paths?: Record<string, string> | null;
    color_theme?: ColorThemeType | null;
    config_mode?: ConfigurationMode | null;
    automatic_mode_ui?: UiNameType | null;
}

export interface MalFullConfiguration {
    base_path: string | null;
    profile: UiProfileType | null;
    custom_model_type_paths: Record<string, string>;
    color_theme: ColorThemeType | null;
    config_mode: ConfigurationMode | null;
    automatic_mode_ui: UiNameType | null;
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
    path: string; // Relative path from the base_path
    type: 'file' | 'directory';
    size: number | null; // Size in bytes, null for directories
    last_modified: string; // ISO Date String
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
    custom_install_path: string;
    set_as_active: boolean;
}

export interface ManagedUiStatus {
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
    ui_name: UiNameType;
    path: string;
    issues_to_fix: string[];
}

export interface UiAdoptionFinalizeRequest {
    ui_name: UiNameType;
    path: string;
}

// --- API Functions ---

// --- UI Management API Functions ---

export const listAvailableUisAPI = async (): Promise<AvailableUiItem[]> => {
    try {
        const response = await apiClient.get<AvailableUiItem[]>('/uis');
        return response.data;
    } catch (error) {
        console.error('Error fetching available UIs:', error);
        throw error;
    }
};

export const getUiStatusesAPI = async (): Promise<AllUiStatusResponse> => {
    try {
        const response = await apiClient.get<AllUiStatusResponse>('/uis/status');
        return response.data;
    } catch (error) {
        console.error('Error fetching UI statuses:', error);
        return { items: [] };
    }
};

export const installUiAPI = async (request: UiInstallRequest): Promise<UiActionResponse> => {
    try {
        const response = await apiClient.post<UiActionResponse>('/uis/install', request);
        return response.data;
    } catch (error) {
        const axiosError = error as any;
        if (axiosError.response?.data?.detail) {
            throw new Error(axiosError.response.data.detail);
        }
        throw error;
    }
};

export const runUiAPI = async (uiName: UiNameType): Promise<UiActionResponse> => {
    try {
        const response = await apiClient.post<UiActionResponse>(`/uis/${uiName}/run`);
        return response.data;
    } catch (error) {
        const axiosError = error as any;
        if (axiosError.response?.data?.detail) {
            throw new Error(axiosError.response.data.detail);
        }
        throw error;
    }
};

export const stopUiAPI = async (taskId: string): Promise<{ success: boolean; message: string }> => {
    try {
        const response = await apiClient.post('/uis/stop', { task_id: taskId });
        return response.data;
    } catch (error) {
        const axiosError = error as any;
        if (axiosError.response?.data?.detail) {
            throw new Error(axiosError.response.data.detail);
        }
        throw error;
    }
};

export const cancelUiTaskAPI = async (
    taskId: string,
): Promise<{ success: boolean; message: string }> => {
    try {
        const response = await apiClient.post('/uis/cancel', {
            task_id: taskId,
        });
        return response.data;
    } catch (error) {
        console.error(`Error cancelling UI task ${taskId}:`, error);
        const axiosError = error as any;
        if (axiosError.response?.data?.detail) {
            throw new Error(axiosError.response.data.detail);
        }
        throw error;
    }
};

export const deleteUiAPI = async (
    uiName: UiNameType,
): Promise<{ success: boolean; message: string }> => {
    try {
        const response = await apiClient.delete(`/uis/${uiName}`);
        return response.data;
    } catch (error) {
        const axiosError = error as any;
        if (axiosError.response?.data?.detail) {
            throw new Error(axiosError.response.data.detail);
        }
        throw error;
    }
};

// --- UI Adoption API Functions ---

export const analyzeUiForAdoptionAPI = async (
    request: UiAdoptionAnalysisRequest,
): Promise<AdoptionAnalysisResponse> => {
    try {
        const response = await apiClient.post<AdoptionAnalysisResponse>(
            '/uis/adopt/analyze',
            request,
        );
        return response.data;
    } catch (error) {
        const axiosError = error as any;
        if (axiosError.response?.data?.detail) {
            throw new Error(axiosError.response.data.detail);
        }
        throw error;
    }
};

export const repairUiAPI = async (request: UiAdoptionRepairRequest): Promise<UiActionResponse> => {
    try {
        const response = await apiClient.post<UiActionResponse>('/uis/adopt/repair', request);
        return response.data;
    } catch (error) {
        const axiosError = error as any;
        if (axiosError.response?.data?.detail) {
            throw new Error(axiosError.response.data.detail);
        }
        throw error;
    }
};

export const finalizeAdoptionAPI = async (
    request: UiAdoptionFinalizeRequest,
): Promise<{ success: boolean; message: string }> => {
    try {
        const response = await apiClient.post('/uis/adopt/finalize', request);
        return response.data;
    } catch (error) {
        const axiosError = error as any;
        if (axiosError.response?.data?.detail) {
            throw new Error(axiosError.response.data.detail);
        }
        throw error;
    }
};

// --- Other API Functions ---

export const searchModels = async (
    params: SearchModelParams,
): Promise<PaginatedModelListResponse> => {
    try {
        const response = await apiClient.get<PaginatedModelListResponse>('/models', { params });
        return response.data;
    } catch (error) {
        console.error('Error in searchModels:', error);
        throw error;
    }
};

export const getModelDetails = async (source: string, modelId: string): Promise<ModelDetails> => {
    try {
        const response = await apiClient.get<ModelDetails>(
            `/models/${encodeURIComponent(source)}/${encodeURIComponent(modelId)}`,
        );
        return response.data;
    } catch (error) {
        console.error('Error in getModelDetails:', error);
        throw error;
    }
};

export const downloadFileAPI = async (
    request: FileDownloadRequest,
): Promise<FileDownloadResponse> => {
    try {
        const response = await apiClient.post<FileDownloadResponse>(
            '/filemanager/download',
            request,
        );
        return response.data;
    } catch (error) {
        console.error('Error in downloadFileAPI:', error);
        const axiosError = error as any;
        if (axiosError.response && axiosError.response.data) {
            return axiosError.response.data;
        }
        throw error;
    }
};

export const cancelDownloadAPI = async (
    downloadId: string,
): Promise<{ success: boolean; message: string }> => {
    try {
        const response = await apiClient.post('/filemanager/download/cancel', {
            download_id: downloadId,
        });
        return response.data;
    } catch (error) {
        console.error(`Error cancelling download ${downloadId}:`, error);
        const axiosError = error as any;
        if (axiosError.response?.data?.detail) {
            throw new Error(axiosError.response.data.detail);
        }
        throw error;
    }
};

export const configurePathsAPI = async (
    config: PathConfigurationRequest,
): Promise<PathConfigurationResponse> => {
    try {
        const response = await apiClient.post<PathConfigurationResponse>(
            '/filemanager/configure',
            config,
        );
        return response.data;
    } catch (error) {
        console.error('Error in configurePathsAPI:', error);
        const axiosError = error as any;
        if (axiosError.response && axiosError.response.data) {
            return axiosError.response.data;
        }
        throw error;
    }
};

export const getCurrentConfigurationAPI = async (): Promise<MalFullConfiguration> => {
    try {
        const response = await apiClient.get<MalFullConfiguration>('/filemanager/configuration');
        return {
            ...response.data,
            custom_model_type_paths: response.data.custom_model_type_paths || {},
            color_theme: response.data.color_theme || 'dark',
            config_mode: response.data.config_mode || 'automatic',
            automatic_mode_ui: response.data.automatic_mode_ui || null,
        };
    } catch (error) {
        console.error('Error fetching current configuration:', error);
        return {
            base_path: null,
            profile: null,
            custom_model_type_paths: {},
            color_theme: 'dark',
            config_mode: 'automatic',
            automatic_mode_ui: null,
        };
    }
};

export const scanHostDirectoriesAPI = async (
    path?: string,
    depth: number = 1,
): Promise<ScanHostDirectoriesResponse> => {
    try {
        const params: Record<string, any> = { max_depth: depth };
        if (path) {
            params.path = path;
        }
        const response = await apiClient.get<ScanHostDirectoriesResponse>(
            '/filemanager/scan-host-directories',
            { params },
        );
        return response.data;
    } catch (error) {
        console.error('Error in scanHostDirectoriesAPI:', error);
        const axiosError = error as any;
        if (axiosError.response && axiosError.response.data) {
            return axiosError.response.data;
        }
        return {
            success: false,
            error: 'Error scanning host directories.',
            data: null,
        };
    }
};

export const listManagedFilesAPI = async (
    relativePath: string | null,
    mode: ViewMode,
): Promise<FileManagerListResponse> => {
    try {
        const response = await apiClient.get<FileManagerListResponse>('/filemanager/files', {
            params: { path: relativePath, mode: mode },
        });
        return response.data;
    } catch (error) {
        console.error('Error listing managed files:', error);
        throw error;
    }
};

export const deleteManagedItemAPI = async (
    relativePath: string,
): Promise<{ success: boolean; message: string }> => {
    try {
        const response = await apiClient.delete<{ success: boolean; message: string }>(
            '/filemanager/files',
            { data: { path: relativePath } },
        );
        return response.data;
    } catch (error) {
        console.error(`Error deleting item at ${relativePath}:`, error);
        const axiosError = error as any;
        if (axiosError.response?.data?.detail) {
            throw new Error(axiosError.response.data.detail);
        }
        throw error;
    }
};

export const getFilePreviewAPI = async (relativePath: string): Promise<FilePreviewResponse> => {
    try {
        const response = await apiClient.get<FilePreviewResponse>('/filemanager/files/preview', {
            params: { path: relativePath },
        });
        return response.data;
    } catch (error) {
        console.error(`Error getting preview for ${relativePath}:`, error);
        const axiosError = error as any;
        if (axiosError.response?.data) {
            return { success: false, path: relativePath, error: axiosError.response.data.detail };
        }
        throw error;
    }
};

export const connectToDownloadTracker = (onMessage: (data: any) => void): WebSocket => {
    const wsUrl = `${WS_BASE_URL}/ws/downloads`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => console.log('WebSocket connection established.');

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            onMessage(data);
        } catch (e) {
            console.error('Error parsing WebSocket message:', e);
        }
    };

    ws.onerror = (event) => {
        console.error('WebSocket error observed:', event);
    };

    ws.onclose = (event) => {
        console.log(
            `WebSocket connection closed. Code: ${event.code}, Reason: '${event.reason}', Was clean: ${event.wasClean}`,
        );
    };

    return ws;
};

export default apiClient;

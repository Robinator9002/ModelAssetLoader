// frontend/src/api/api.tsx
import axios, { type AxiosInstance } from "axios";

const API_BASE_URL = "http://localhost:8000/api";
const WS_BASE_URL = "ws://localhost:8000";

const apiClient: AxiosInstance = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        "Content-Type": "application/json",
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
    sort?: "lastModified" | "downloads" | "likes" | "author" | "id";
    direction?: -1 | 1;
    limit?: number;
    page?: number;
}

// --- FileManager & Download Interfaces ---
export type UiProfileType = "ComfyUI" | "A1111" | "ForgeUI" | "Custom";
export type ColorThemeType = "dark" | "light";
export type ModelType =
    | "checkpoints"
    | "loras"
    | "vae"
    | "clip"
    | "unet"
    | "controlnet"
    | "embeddings"
    | "hypernetworks"
    | "diffusers"
    | "custom";

export interface PathConfigurationRequest {
    base_path?: string | null;
    profile?: UiProfileType | null;
    custom_model_type_paths?: Record<string, string> | null;
    color_theme?: ColorThemeType | null;
}

export interface MalFullConfiguration {
    base_path: string | null;
    profile: UiProfileType | null;
    custom_model_type_paths: Record<string, string>;
    color_theme: ColorThemeType | null;
}

export interface PathConfigurationResponse {
    success: boolean;
    message?: string | null;
    error?: string | null;
    configured_base_path?: string | null;
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
    status: "pending" | "downloading" | "completed" | "error" | "cancelled";
    progress: number;
    total_size_bytes: number;
    downloaded_bytes: number;
    error_message?: string | null;
    target_path?: string | null;
}

// --- Host Directory Scanning Interfaces ---
export interface HostDirectoryItem {
    name: string;
    path: string;
    type: "directory";
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
    type: "file" | "directory";
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

// --- API Functions (Existing) ---
export const searchModels = async (
    params: SearchModelParams
): Promise<PaginatedModelListResponse> => {
    try {
        const response = await apiClient.get<PaginatedModelListResponse>("/models", { params });
        return response.data;
    } catch (error) {
        console.error("Error in searchModels:", error);
        throw error;
    }
};

export const getModelDetails = async (
    source: string,
    modelId: string
): Promise<ModelDetails> => {
    try {
        const response = await apiClient.get<ModelDetails>(
            `/models/${encodeURIComponent(source)}/${encodeURIComponent(modelId)}`
        );
        return response.data;
    } catch (error) {
        console.error("Error in getModelDetails:", error);
        throw error;
    }
};

export const downloadFileAPI = async (
    request: FileDownloadRequest
): Promise<FileDownloadResponse> => {
    try {
        const response = await apiClient.post<FileDownloadResponse>("/filemanager/download", request);
        return response.data;
    } catch (error) {
        console.error("Error in downloadFileAPI:", error);
        const axiosError = error as any;
        if (axiosError.response && axiosError.response.data) {
            return axiosError.response.data;
        }
        throw error;
    }
};

export const cancelDownloadAPI = async (downloadId: string): Promise<{ success: boolean; message?: string }> => {
    try {
        const response = await apiClient.post(`/filemanager/downloads/${downloadId}/cancel`);
        return { success: true, ...response.data };
    } catch (error) {
        console.error(`Failed to cancel download ${downloadId}:`, error);
        const axiosError = error as any;
        if (axiosError.response?.data?.detail) {
             throw new Error(axiosError.response.data.detail);
        }
        throw error;
    }
};

export const dismissDownloadAPI = async (downloadId: string): Promise<void> => {
    try {
        await apiClient.delete(`/filemanager/downloads/${downloadId}`);
    } catch (error) {
        console.error(`Failed to dismiss download ${downloadId}:`, error);
        throw error;
    }
};

export const configurePathsAPI = async (
    config: PathConfigurationRequest
): Promise<PathConfigurationResponse> => {
    try {
        const response = await apiClient.post<PathConfigurationResponse>("/filemanager/configure", config);
        return response.data;
    } catch (error) {
        console.error("Error in configurePathsAPI:", error);
        const axiosError = error as any;
        if (axiosError.response && axiosError.response.data) {
            return axiosError.response.data;
        }
        throw error;
    }
};

export const getCurrentConfigurationAPI =
    async (): Promise<MalFullConfiguration> => {
        try {
            const response = await apiClient.get<MalFullConfiguration>("/filemanager/configuration");
            return {
                ...response.data,
                custom_model_type_paths: response.data.custom_model_type_paths || {},
                color_theme: response.data.color_theme || "dark",
            };
        } catch (error) {
            console.error("Error fetching current configuration:", error);
            return {
                base_path: null,
                profile: null,
                custom_model_type_paths: {},
                color_theme: "dark",
            };
        }
    };

export const scanHostDirectoriesAPI = async (
    path?: string,
    depth: number = 1
): Promise<ScanHostDirectoriesResponse> => {
    try {
        const params: Record<string, any> = { max_depth: depth };
        if (path) {
            params.path = path;
        }
        const response = await apiClient.get<ScanHostDirectoriesResponse>(
            "/filemanager/scan-host-directories",
            { params }
        );
        return response.data;
    } catch (error) {
        console.error("Error in scanHostDirectoriesAPI:", error);
        const axiosError = error as any;
        if (axiosError.response && axiosError.response.data) {
            return axiosError.response.data;
        }
        return {
            success: false,
            error: "Error scanning host directories.",
            data: null,
        };
    }
};

// --- API Functions for Local File Management ---

/**
 * Lists files and directories, supporting different view modes.
 * @param relativePath The relative path from the base_path. If null, the root is listed.
 * @param mode The view mode ('models' or 'explorer') to request from the backend.
 */
export const listManagedFilesAPI = async (relativePath: string | null, mode: ViewMode): Promise<FileManagerListResponse> => {
    try {
        // The generic type here now correctly expects the new response shape
        const response = await apiClient.get<FileManagerListResponse>('/filemanager/files', {
            params: { 
                path: relativePath,
                mode: mode
            }
        });
        return response.data;
    } catch (error) {
        console.error('Error listing managed files:', error);
        throw error;
    }
};

/**
 * Deletes a file or directory at a specific relative path.
 * @param relativePath The relative path of the item to be deleted.
 */
export const deleteManagedItemAPI = async (relativePath: string): Promise<{ success: boolean; message: string }> => {
    try {
        const response = await apiClient.delete<{ success: boolean; message: string }>('/filemanager/files', {
            data: { path: relativePath } // DELETE requests with a body use the 'data' field in Axios
        });
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

/**
 * Gets a preview of a text file's content.
 * @param relativePath The relative path to the file.
 */
export const getFilePreviewAPI = async (relativePath: string): Promise<FilePreviewResponse> => {
    try {
        const response = await apiClient.get<FilePreviewResponse>('/filemanager/files/preview', {
            params: { path: relativePath }
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


// --- WebSocket Connection (Unchanged) ---
export const connectToDownloadTracker = (
    onMessage: (data: any) => void
): WebSocket => {
    const wsUrl = `${WS_BASE_URL}/ws/downloads`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => console.log("WebSocket connection established.");

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            onMessage(data);
        } catch (e) {
            console.error("Error parsing WebSocket message:", e);
        }
    };

    ws.onerror = (event) => {
        console.error("WebSocket error observed:", event);
    };

    ws.onclose = (event) => {
        console.log(
            `WebSocket connection closed. Code: ${event.code}, Reason: '${event.reason}', Was clean: ${event.wasClean}`
        );
    };

    return ws;
};

export default apiClient;

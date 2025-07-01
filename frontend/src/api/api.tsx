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

// --- Generic Model Interfaces (REFACTOR) ---
// Note: Renamed from HFModel... to Model... and added 'source' field.

export interface ModelFile {
    rfilename: string;
    size?: number | null;
}

export interface ModelListItem {
    id: string;
    source: string; // <-- ADDED: The source of the model (e.g., 'huggingface')
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
    source?: string; // <-- ADDED: The source to search in
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
    source: string; // <-- ADDED: The source of the model
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
    download_id?: string | null; // <-- ADDED: The tracker ID
}

// --- Download Tracker WebSocket Interface ---
export interface DownloadStatus {
    download_id: string;
    filename: string;
    repo_id: string;
    status: "pending" | "downloading" | "completed" | "error";
    progress: number; // 0.0 to 100.0
    total_size_bytes: number;
    downloaded_bytes: number;
    error_message?: string | null;
    target_path?: string | null;
}

// --- Interfaces for Host Directory Scanning ---
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

// --- API Functions (REFACTOR) ---

export const searchModels = async (
    params: SearchModelParams
): Promise<PaginatedModelListResponse> => {
    try {
        // REFACTOR: The 'source' is now part of the params object.
        const response = await apiClient.get<PaginatedModelListResponse>(
            "/models", // Endpoint is now singular '/models'
            { params }
        );
        console.log("searchModels response:", response.data);
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
        // REFACTOR: The endpoint now includes the source and the full modelId.
        const response = await apiClient.get<ModelDetails>(
            `/models/${encodeURIComponent(source)}/${encodeURIComponent(
                modelId
            )}`
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
        // REFACTOR: The request payload now includes the source.
        const response = await apiClient.post<FileDownloadResponse>(
            "/filemanager/download",
            request
        );
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

// Function to permanently dismiss a download from the tracker
export const dismissDownloadAPI = async (downloadId: string): Promise<void> => {
    try {
        await apiClient.delete(`/filemanager/downloads/${downloadId}`);
    } catch (error) {
        console.error(`Failed to dismiss download ${downloadId}:`, error);
        // Optionally re-throw or handle the error in the UI
        throw error;
    }
};

export const configurePathsAPI = async (
    config: PathConfigurationRequest
): Promise<PathConfigurationResponse> => {
    try {
        const response = await apiClient.post<PathConfigurationResponse>(
            "/filemanager/configure",
            config
        );
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
            const response = await apiClient.get<MalFullConfiguration>(
                "/filemanager/configuration"
            );
            return {
                ...response.data,
                custom_model_type_paths:
                    response.data.custom_model_type_paths || {},
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
            error: "Fehler beim Scannen der Host-Verzeichnisse.",
            data: null,
        };
    }
};

// --- WebSocket Connection ---
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

    // REFACTOR: Add detailed close event logging
    ws.onclose = (event) => {
        console.log(
            `WebSocket connection closed. Code: ${event.code}, Reason: '${event.reason}', Was clean: ${event.wasClean}`
        );
    };

    return ws;
};

export default apiClient;

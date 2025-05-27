// frontend/src/api/api.tsx
import axios, { type AxiosInstance } from "axios";

const API_BASE_URL = "http://localhost:8000/api";

const apiClient: AxiosInstance = axios.create({
	baseURL: API_BASE_URL,
	headers: {
		"Content-Type": "application/json",
	},
});

// --- Existing Interfaces ---
export interface HFModelFile {
	rfilename: string;
	size?: number | null;
}
export interface HFModelListItem {
	id: string;
	author?: string | null;
	model_name: string;
	lastModified?: string | null; // ISO Date String
	tags: string[];
	pipeline_tag?: string | null;
	downloads?: number | null;
	likes?: number | null;
}
export interface PaginatedModelListResponse {
	items: HFModelListItem[];
	page: number;
	limit: number;
	has_more: boolean;
}
export interface HFModelDetails extends HFModelListItem {
	sha?: string | null;
	private?: boolean | null;
	gated?: string | null;
	library_name?: string | null;
	siblings: HFModelFile[];
	readme_content?: string | null;
}
export interface SearchModelParams {
	search?: string;
	author?: string;
	tags?: string[]; // Wird als Array von Strings gesendet, FastAPI verarbeitet das
	sort?: "lastModified" | "downloads" | "likes" | "author" | "id";
	direction?: -1 | 1;
	limit?: number;
	page?: number;
}

// --- FileManager Interfaces ---
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
export interface PathConfigurationResponse {
	success: boolean;
	message?: string | null;
	error?: string | null;
	configured_base_path?: string | null;
	current_config?: MalFullConfiguration | null; // Backend sendet jetzt die volle Konfig zurück
}
export interface FileDownloadRequest {
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
	path?: string | null;
}
export interface DirectoryItem {
	name: string;
	path: string; // Relative path for this type
	type: "file" | "directory";
	children?: DirectoryItem[] | null;
}
export interface DirectoryStructureResponse {
	success: boolean;
	structure?: DirectoryItem[] | null;
	error?: string | null;
	base_path_configured: boolean;
}
export interface RescanPathRequest {
	path?: string | null;
}
export interface RescanPathResponse {
	success: boolean;
	message?: string | null;
	error?: string | null;
}

export interface MalFullConfiguration {
	base_path: string | null;
	profile: UiProfileType | null;
	custom_model_type_paths: Record<string, string>;
	color_theme: ColorThemeType | null;
}

// --- Interfaces for Host Directory Scanning ---
export interface HostDirectoryItem {
	name: string;
	path: string; // Absolute path on the host system
	type: "directory"; // Only directories
	children?: HostDirectoryItem[] | null;
}

export interface ScanHostDirectoriesResponse {
	success: boolean;
	message?: string | null;
	error?: string | null;
	data?: HostDirectoryItem[] | null; // List of scanned root directories
}


// --- API Functions ---
export const searchModels = async (
	params: SearchModelParams
): Promise<PaginatedModelListResponse> => {
	try {
		// Für FastAPI: Wenn tags ein Array ist, muss es für jeden Wert einen separaten Query-Parameter geben
        // Axios' default Serializer macht das normalerweise korrekt (tags=tag1&tags=tag2)
		const response = await apiClient.get<PaginatedModelListResponse>(
			"/models/",
			{ params } // Axios kümmert sich um die korrekte Formatierung von Array-Query-Parametern
		);
		console.log("searchModels response:", response.data);
		return response.data;
	} catch (error) {
		console.error("Error in searchModels:", error);
		throw error;
	}
};
export const getModelDetails = async (
	author: string,
	modelName: string
): Promise<HFModelDetails> => {
	try {
		const response = await apiClient.get<HFModelDetails>(
			`/models/${encodeURIComponent(author)}/${encodeURIComponent(modelName)}`
		);
		return response.data;
	} catch (error) {
		console.error("Error in getModelDetails:", error);
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
		// Hier wäre es gut, den Fehler spezifischer zu behandeln oder weiterzugeben,
		// damit die UI darauf reagieren kann.
		const axiosError = error as any;
		if (axiosError.response && axiosError.response.data) {
			return axiosError.response.data; // Oft enthält dies die Fehlerdetails vom Backend
		}
		throw error; // Fallback
	}
};
export const downloadFileAPI = async (
	request: FileDownloadRequest
): Promise<FileDownloadResponse> => {
	try {
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
export const getFolderStructureAPI = async (
	relativePath?: string,
	depth: number = 1
): Promise<DirectoryStructureResponse> => {
	try {
		const params: Record<string, any> = { depth };
		if (relativePath) params.relative_path = relativePath;
		const response = await apiClient.get<DirectoryStructureResponse>(
			"/filemanager/list-directory",
			{ params }
		);
		console.log("getFolderStructureAPI response:", response.data);
		return response.data;
	} catch (error) {
		console.error("Error in getFolderStructureAPI:", error);
		const axiosError = error as any;
		if (axiosError.response && axiosError.response.data) {
			return axiosError.response.data;
		}
		// Fallback für den Fall, dass base_path nicht konfiguriert ist und das Backend direkt einen Fehler wirft
		// oder für andere Netzwerkfehler.
		return {
			success: false,
			error: "Fehler beim Abrufen der Ordnerstruktur.",
			base_path_configured: false, // Annahme, wenn ein Fehler auftritt
			structure: null
		};
	}
};
export const rescanFolderStructureAPI = async (
	path?: string
): Promise<RescanPathResponse> => {
	try {
		const payload: RescanPathRequest = {};
		if (path) payload.path = path;
		const response = await apiClient.post<RescanPathResponse>(
			"/filemanager/rescan-path",
			payload
		);
		return response.data;
	} catch (error) {
		console.error("Error in rescanFolderStructureAPI:", error);
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
				custom_model_type_paths: response.data.custom_model_type_paths || {},
				color_theme: response.data.color_theme || "dark",
			};
		} catch (error) {
			console.error("Error fetching current configuration:", error);
			// Sinnvoller Fallback, damit die App nicht crasht
			return {
				base_path: null,
				profile: null,
				custom_model_type_paths: {},
				color_theme: "dark",
			};
		}
	};

// --- NEUE API FUNKTION für Host Directory Scan ---
export const scanHostDirectoriesAPI = async (
	path?: string, // Optional: spezifischer Pfad zum Scannen
	depth: number = 1 // Default-Tiefe
): Promise<ScanHostDirectoriesResponse> => {
	try {
		const params: Record<string, any> = { max_depth: depth }; // FastAPI erwartet 'max_depth'
		if (path) {
			params.path = path; // FastAPI erwartet 'path' als Alias für path_to_scan
		}
		
		const response = await apiClient.get<ScanHostDirectoriesResponse>(
			"/filemanager/scan-host-directories",
			{ params }
		);
		console.log("scanHostDirectoriesAPI response:", response.data);
		return response.data;
	} catch (error) {
		console.error("Error in scanHostDirectoriesAPI:", error);
		const axiosError = error as any;
		if (axiosError.response && axiosError.response.data) {
			// Wenn das Backend eine strukturierte Fehlermeldung sendet
			return axiosError.response.data;
		}
		// Allgemeiner Fehler
		return {
			success: false,
			error: "Fehler beim Scannen der Host-Verzeichnisse.",
			data: null,
		};
	}
};


export default apiClient;

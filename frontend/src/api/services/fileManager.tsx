// frontend/src/api/services/fileManager.tsx
import apiClient from '../client';
import type {
    FileDownloadRequest,
    FileDownloadResponse,
    PathConfigurationRequest,
    PathConfigurationResponse,
    MalFullConfiguration,
    ScanHostDirectoriesResponse,
    FileManagerListResponse,
    ViewMode,
    FilePreviewResponse,
} from '../types';

/**
 * @file This module handles all API interactions related to file management.
 * This includes downloading models, managing local files and directories,
 * configuring paths, and scanning the host system.
 */

// --- File Manager & Downloads API ---

/**
 * Initiates a file download from a source repository.
 * @param {FileDownloadRequest} request - The details of the file to be downloaded.
 * @returns {Promise<FileDownloadResponse>} A promise that resolves with the download status and ID.
 * @throws Will throw a specific error message if the API returns one, otherwise a generic error.
 */
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
        const axiosError = error as any;
        if (axiosError.response && axiosError.response.data?.detail) {
            throw new Error(axiosError.response.data.detail);
        }
        throw error;
    }
};

/**
 * Sends a request to cancel an in-progress download.
 * @param {string} downloadId - The unique identifier of the download to cancel.
 * @returns {Promise<{ success: boolean; message: string }>} A promise that resolves with a success status and message.
 * @throws Will throw a specific error message if the API returns one, otherwise a generic error.
 */
export const cancelDownloadAPI = async (
    downloadId: string,
): Promise<{ success: boolean; message: string }> => {
    try {
        const response = await apiClient.post('/filemanager/download/cancel', {
            download_id: downloadId,
        });
        return response.data;
    } catch (error) {
        const axiosError = error as any;
        if (axiosError.response?.data?.detail) {
            throw new Error(axiosError.response.data.detail);
        }
        throw error;
    }
};

/**
 * Dismisses a completed or failed download from the tracker.
 * @param {string} downloadId - The unique identifier of the download to dismiss.
 * @returns {Promise<{ success: boolean; message: string }>} A promise that resolves with a success status and message.
 * @throws Will throw a specific error message if the API returns one, otherwise a generic error.
 */
export const dismissDownloadAPI = async (
    downloadId: string,
): Promise<{ success: boolean; message: string }> => {
    try {
        const response = await apiClient.post('/filemanager/download/dismiss', {
            download_id: downloadId,
        });
        return response.data;
    } catch (error) {
        console.error(`Error dismissing download ${downloadId}:`, error);
        const axiosError = error as any;
        if (axiosError.response?.data?.detail) {
            throw new Error(axiosError.response.data.detail);
        }
        throw error;
    }
};

/**
 * Configures the base paths and model type paths for the file manager.
 * @param {PathConfigurationRequest} config - The configuration settings to apply.
 * @returns {Promise<PathConfigurationResponse>} A promise that resolves with the result of the operation.
 * @throws Will throw a specific error message if the API returns one, otherwise a generic error.
 */
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
        const axiosError = error as any;
        if (axiosError.response && axiosError.response.data?.detail) {
            throw new Error(axiosError.response.data.detail);
        }
        throw error;
    }
};

/**
 * Fetches the current, complete configuration from the server.
 * @returns {Promise<MalFullConfiguration>} A promise that resolves to the full configuration object.
 * @throws Will throw an error if the network request fails.
 */
export const getCurrentConfigurationAPI = async (): Promise<MalFullConfiguration> => {
    try {
        const response = await apiClient.get<MalFullConfiguration>('/filemanager/configuration');
        return response.data;
    } catch (error) {
        console.error('Error fetching current configuration:', error);
        throw error;
    }
};

/**
 * Fetches known UI profiles from the backend. This eliminates hardcoded constants
 * in the frontend, making the backend the single source of truth for model path structures.
 * @returns {Promise<Record<string, Record<string, string>>>} A promise that resolves to a map of UI profiles.
 * @throws Will throw an error if the network request fails.
 */
export const getKnownUiProfilesAPI = async (): Promise<Record<string, Record<string, string>>> => {
    try {
        const response = await apiClient.get('/filemanager/known-ui-profiles');
        return response.data;
    } catch (error) {
        console.error('Error fetching known UI profiles:', error);
        throw error;
    }
};

/**
 * Scans host directories to a specified depth.
 * @param {string} [path] - The starting path to scan. Defaults to the root if not provided.
 * @param {number} [depth=1] - The maximum depth to scan.
 * @returns {Promise<ScanHostDirectoriesResponse>} A promise that resolves with the directory structure.
 * @throws Will throw a specific error message if the API returns one, or a generic error.
 */
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
        const axiosError = error as any;
        if (axiosError.response && axiosError.response.data?.detail) {
            throw new Error(axiosError.response.data.detail);
        }
        throw new Error('An unknown error occurred while scanning directories.');
    }
};

/**
 * Lists files and directories within a specified managed path.
 * @param {string | null} relativePath - The path relative to the managed base directory.
 * @param {ViewMode} mode - The view mode ('models' or 'explorer').
 * @returns {Promise<FileManagerListResponse>} A promise that resolves with the list of items.
 * @throws Will throw an error if the network request fails.
 */
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

/**
 * Deletes a file or directory from the managed file system.
 * @param {string} relativePath - The path of the item to delete, relative to the managed base directory.
 * @returns {Promise<{ success: boolean; message: string }>} A promise that resolves with a success status and message.
 * @throws Will throw a specific error message if the API returns one, otherwise a generic error.
 */
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
        const axiosError = error as any;
        if (axiosError.response?.data?.detail) {
            throw new Error(axiosError.response.data.detail);
        }
        throw error;
    }
};

/**
 * Fetches a preview of a file's content (e.g., for text files).
 * @param {string} relativePath - The path of the file to preview.
 * @returns {Promise<FilePreviewResponse>} A promise that resolves with the file content or an error.
 * @throws Will throw a specific error message if the API returns one, otherwise a generic error.
 */
export const getFilePreviewAPI = async (relativePath: string): Promise<FilePreviewResponse> => {
    try {
        const response = await apiClient.get<FilePreviewResponse>('/filemanager/files/preview', {
            params: { path: relativePath },
        });
        return response.data;
    } catch (error) {
        const axiosError = error as any;
        if (axiosError.response?.data?.detail) {
            throw new Error(axiosError.response.data.detail);
        }
        throw error;
    }
};

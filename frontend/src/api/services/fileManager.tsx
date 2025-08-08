// frontend/src/api/services/fileManager.tsx
import apiClient from '../client';
import { handleApiError } from '../errorHandler';
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
 * @throws Will throw a standardized error from handleApiError.
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
        throw handleApiError(error, 'Failed to start file download.');
    }
};

/**
 * Sends a request to cancel an in-progress download.
 * @param {string} downloadId - The unique identifier of the download to cancel.
 * @returns {Promise<{ success: boolean; message: string }>} A promise that resolves with a success status and message.
 * @throws Will throw a standardized error from handleApiError.
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
        throw handleApiError(error, 'Failed to cancel download.');
    }
};

/**
 * Dismisses a completed or failed download from the tracker.
 * @param {string} downloadId - The unique identifier of the download to dismiss.
 * @returns {Promise<{ success: boolean; message: string }>} A promise that resolves with a success status and message.
 * @throws Will throw a standardized error from handleApiError.
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
        throw handleApiError(error, 'Failed to dismiss task.');
    }
};

/**
 * Configures the base paths and model type paths for the file manager.
 * @param {PathConfigurationRequest} config - The configuration settings to apply.
 * @returns {Promise<PathConfigurationResponse>} A promise that resolves with the result of the operation.
 * @throws Will throw a standardized error from handleApiError.
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
        throw handleApiError(error, 'Failed to save configuration.');
    }
};

/**
 * Fetches the current, complete configuration from the server.
 * @returns {Promise<MalFullConfiguration>} A promise that resolves to the full configuration object.
 * @throws Will throw a standardized error from handleApiError.
 */
export const getCurrentConfigurationAPI = async (): Promise<MalFullConfiguration> => {
    try {
        const response = await apiClient.get<MalFullConfiguration>('/filemanager/configuration');
        return response.data;
    } catch (error) {
        console.error('Error fetching current configuration:', error);
        throw handleApiError(error, 'Failed to load application configuration.');
    }
};

/**
 * Fetches known UI profiles from the backend. This eliminates hardcoded constants
 * in the frontend, making the backend the single source of truth for model path structures.
 * @returns {Promise<Record<string, Record<string, string>>>} A promise that resolves to a map of UI profiles.
 * @throws Will throw a standardized error from handleApiError.
 */
export const getKnownUiProfilesAPI = async (): Promise<Record<string, Record<string, string>>> => {
    try {
        const response = await apiClient.get('/filemanager/known-ui-profiles');
        return response.data;
    } catch (error) {
        console.error('Error fetching known UI profiles:', error);
        throw handleApiError(error, 'Failed to fetch UI profiles.');
    }
};

/**
 * Scans host directories to a specified depth.
 * @param {string} [path] - The starting path to scan. Defaults to the root if not provided.
 * @param {number} [depth=1] - The maximum depth to scan.
 * @returns {Promise<ScanHostDirectoriesResponse>} A promise that resolves with the directory structure.
 * @throws Will throw a standardized error from handleApiError.
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
        throw handleApiError(error, 'An unknown error occurred while scanning directories.');
    }
};

/**
 * Lists files and directories within a specified managed path.
 * @param {string | null} relativePath - The path relative to the managed base directory.
 * @param {ViewMode} mode - The view mode ('models' or 'explorer').
 * @returns {Promise<FileManagerListResponse>} A promise that resolves with the list of items.
 * @throws Will throw a standardized error from handleApiError.
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
        throw handleApiError(error, 'Failed to list managed files.');
    }
};

/**
 * Deletes a file or directory from the managed file system.
 * @param {string} relativePath - The path of the item to delete, relative to the managed base directory.
 * @returns {Promise<{ success: boolean; message: string }>} A promise that resolves with a success status and message.
 * @throws Will throw a standardized error from handleApiError.
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
        throw handleApiError(error, 'Failed to delete item.');
    }
};

/**
 * Fetches a preview of a file's content (e.g., for text files).
 * @param {string} relativePath - The path of the file to preview.
 * @returns {Promise<FilePreviewResponse>} A promise that resolves with the file content or an error.
 * @throws Will throw a standardized error from handleApiError.
 */
export const getFilePreviewAPI = async (relativePath: string): Promise<FilePreviewResponse> => {
    try {
        const response = await apiClient.get<FilePreviewResponse>('/filemanager/files/preview', {
            params: { path: relativePath },
        });
        return response.data;
    } catch (error) {
        throw handleApiError(error, 'Failed to get file preview.');
    }
};

// frontend/src/api/services/ui.tsx
import apiClient from '../client';
import { handleApiError } from '../errorHandler';
import type {
    AvailableUiItem,
    AllUiStatusResponse,
    UiInstallRequest,
    UiActionResponse,
    AdoptionAnalysisResponse,
    UiAdoptionAnalysisRequest,
    UiAdoptionRepairRequest,
    UiAdoptionFinalizeRequest,
} from '../types';

/**
 * @file This module centralizes all API functions related to User Interface (UI)
 * management and adoption. This includes listing, installing, running, stopping,
 * and deleting UIs, as well as handling the adoption process for existing instances.
 */

// --- UI Management API Functions ---

/**
 * Fetches the list of all available UIs that can be installed.
 * @returns {Promise<AvailableUiItem[]>} A promise that resolves to an array of available UI items.
 * @throws Will throw a standardized error from handleApiError.
 */
export const listAvailableUisAPI = async (): Promise<AvailableUiItem[]> => {
    try {
        const response = await apiClient.get<AvailableUiItem[]>('/uis');
        return response.data;
    } catch (error) {
        console.error('Error fetching available UIs:', error);
        throw handleApiError(error, 'Failed to fetch available UIs.');
    }
};

/**
 * Fetches the current status of all managed UIs (e.g., installed, running).
 * @returns {Promise<AllUiStatusResponse>} A promise that resolves to an object containing the statuses.
 * @throws Will throw a standardized error from handleApiError.
 */
export const getUiStatusesAPI = async (): Promise<AllUiStatusResponse> => {
    try {
        const response = await apiClient.get<AllUiStatusResponse>('/uis/status');
        return response.data;
    } catch (error) {
        console.error('Error fetching UI statuses:', error);
        throw handleApiError(error, 'Failed to fetch UI statuses.');
    }
};

/**
 * Sends a request to install a specific UI.
 * @param {UiInstallRequest} request - The details of the UI to install.
 * @returns {Promise<UiActionResponse>} A promise that resolves with the response from the server, including a task ID.
 * @throws Will throw a standardized error from handleApiError.
 */
export const installUiAPI = async (request: UiInstallRequest): Promise<UiActionResponse> => {
    try {
        const response = await apiClient.post<UiActionResponse>('/uis/install', request);
        return response.data;
    } catch (error) {
        throw handleApiError(error, 'Failed to start UI installation.');
    }
};

/**
 * @refactor {CRITICAL} Updated function to accept `installationId` instead of `uiName`.
 * This aligns with the backend's instance-based routing.
 *
 * Sends a request to run an installed UI instance.
 * @param {string} installationId - The unique ID of the UI instance to run.
 * @returns {Promise<UiActionResponse>} A promise that resolves with the response from the server, including a task ID.
 * @throws Will throw a standardized error from handleApiError.
 */
export const runUiAPI = async (installationId: string): Promise<UiActionResponse> => {
    try {
        const response = await apiClient.post<UiActionResponse>(`/uis/run/${installationId}`);
        return response.data;
    } catch (error) {
        throw handleApiError(error, 'Failed to start UI.');
    }
};

/**
 * Sends a request to stop a running UI task.
 * @param {string} taskId - The ID of the running task to stop.
 * @returns {Promise<{ success: boolean; message: string }>} A promise that resolves with a success status and message.
 * @throws Will throw a standardized error from handleApiError.
 */
export const stopUiAPI = async (taskId: string): Promise<{ success: boolean; message: string }> => {
    try {
        const response = await apiClient.post('/uis/stop', { task_id: taskId });
        return response.data;
    } catch (error) {
        throw handleApiError(error, 'Failed to stop UI.');
    }
};

/**
 * Sends a request to cancel an ongoing UI-related task (e.g., installation).
 * @param {string} taskId - The ID of the task to cancel.
 * @returns {Promise<{ success: boolean; message: string }>} A promise that resolves with a success status and message.
 * @throws Will throw a standardized error from handleApiError.
 */
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
        throw handleApiError(error, 'Failed to cancel UI task.');
    }
};

/**
 * @refactor {CRITICAL} Updated function to accept `installationId` instead of `uiName`.
 * This aligns with the backend's instance-based routing for deletion.
 *
 * Sends a request to delete/uninstall a UI instance.
 * @param {string} installationId - The unique ID of the UI instance to delete.
 * @returns {Promise<{ success: boolean; message: string }>} A promise that resolves with a success status and message.
 * @throws Will throw a standardized error from handleApiError.
 */
export const deleteUiAPI = async (
    installationId: string,
): Promise<{ success: boolean; message: string }> => {
    try {
        const response = await apiClient.delete(`/uis/${installationId}`);
        return response.data;
    } catch (error) {
        throw handleApiError(error, 'Failed to delete UI environment.');
    }
};

// --- UI Adoption API Functions ---

/**
 * Analyzes an existing UI installation to check if it can be "adopted" and managed.
 * @param {UiAdoptionAnalysisRequest} request - The details of the UI path to analyze.
 * @returns {Promise<AdoptionAnalysisResponse>} A promise that resolves with the analysis results.
 * @throws Will throw a standardized error from handleApiError.
 */
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
        throw handleApiError(error, 'Failed to analyze UI for adoption.');
    }
};

/**
 * Sends a request to repair issues found during the adoption analysis.
 * @param {UiAdoptionRepairRequest} request - The details of the UI and the issues to fix.
 * @returns {Promise<UiActionResponse>} A promise that resolves with the response from the server, including a task ID.
 * @throws Will throw a standardized error from handleApiError.
 */
export const repairUiAPI = async (request: UiAdoptionRepairRequest): Promise<UiActionResponse> => {
    try {
        const response = await apiClient.post<UiActionResponse>('/uis/adopt/repair', request);
        return response.data;
    } catch (error) {
        throw handleApiError(error, 'Failed to start UI repair.');
    }
};

/**
 * Finalizes the adoption process for a UI, making it fully managed.
 * @param {UiAdoptionFinalizeRequest} request - The details of the UI to finalize.
 * @returns {Promise<{ success: boolean; message: string }>} A promise that resolves with a success status and message.
 * @throws Will throw a standardized error from handleApiError.
 */
export const finalizeAdoptionAPI = async (
    request: UiAdoptionFinalizeRequest,
): Promise<{ success: boolean; message: string }> => {
    try {
        const response = await apiClient.post('/uis/adopt/finalize', request);
        return response.data;
    } catch (error) {
        throw handleApiError(error, 'Failed to finalize UI adoption.');
    }
};

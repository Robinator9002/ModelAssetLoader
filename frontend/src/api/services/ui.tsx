// frontend/src/api/services/ui.tsx
import apiClient from '../client';
import { handleApiError } from '../errorHandler';
import type {
    AvailableUiItem,
    AllUiStatusResponse,
    UiInstallRequest,
    UiActionResponse,
    UpdateUiInstanceRequest, // --- NEW: Import the type ---
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

export const listAvailableUisAPI = async (): Promise<AvailableUiItem[]> => {
    try {
        const response = await apiClient.get<AvailableUiItem[]>('/uis');
        return response.data;
    } catch (error) {
        console.error('Error fetching available UIs:', error);
        throw handleApiError(error, 'Failed to fetch available UIs.');
    }
};

export const getUiStatusesAPI = async (): Promise<AllUiStatusResponse> => {
    try {
        const response = await apiClient.get<AllUiStatusResponse>('/uis/status');
        return response.data;
    } catch (error) {
        console.error('Error fetching UI statuses:', error);
        throw handleApiError(error, 'Failed to fetch UI statuses.');
    }
};

export const installUiAPI = async (request: UiInstallRequest): Promise<UiActionResponse> => {
    try {
        const response = await apiClient.post<UiActionResponse>('/uis/install', request);
        return response.data;
    } catch (error) {
        throw handleApiError(error, 'Failed to start UI installation.');
    }
};

// --- NEW: API function to update a UI instance ---
export const updateUiInstanceAPI = async (
    installationId: string,
    data: UpdateUiInstanceRequest,
): Promise<{ success: boolean; message: string }> => {
    try {
        const response = await apiClient.put(`/uis/${installationId}`, data);
        return response.data;
    } catch (error) {
        throw handleApiError(error, 'Failed to update UI instance.');
    }
};

export const runUiAPI = async (installationId: string): Promise<UiActionResponse> => {
    try {
        const response = await apiClient.post<UiActionResponse>(`/uis/run/${installationId}`);
        return response.data;
    } catch (error) {
        throw handleApiError(error, 'Failed to start UI.');
    }
};

export const stopUiAPI = async (taskId: string): Promise<{ success: boolean; message: string }> => {
    try {
        const response = await apiClient.post('/uis/stop', { task_id: taskId });
        return response.data;
    } catch (error) {
        throw handleApiError(error, 'Failed to stop UI.');
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
        throw handleApiError(error, 'Failed to cancel UI task.');
    }
};

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

export const repairUiAPI = async (request: UiAdoptionRepairRequest): Promise<UiActionResponse> => {
    try {
        const response = await apiClient.post<UiActionResponse>('/uis/adopt/repair', request);
        return response.data;
    } catch (error) {
        throw handleApiError(error, 'Failed to start UI repair.');
    }
};

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

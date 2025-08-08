// frontend/src/api/services/models.tsx
import apiClient from '../client';
import { handleApiError } from '../errorHandler';
import type { SearchModelParams, PaginatedModelListResponse, ModelDetails } from '../types';

/**
 * @file This module is responsible for all API interactions related to
 * browsing, searching, and retrieving details for models.
 */

// --- Model Search & Details API ---

/**
 * Searches for models based on a variety of filter criteria.
 * @param {SearchModelParams} params - The parameters for the search query, including filters, sorting, and pagination.
 * @returns {Promise<PaginatedModelListResponse>} A promise that resolves to a paginated list of models.
 * @throws Will throw a standardized error from handleApiError.
 */
export const searchModels = async (
    params: SearchModelParams,
): Promise<PaginatedModelListResponse> => {
    try {
        const response = await apiClient.get<PaginatedModelListResponse>('/models', { params });
        return response.data;
    } catch (error) {
        console.error('Error in searchModels:', error);
        throw handleApiError(error, 'Failed to search for models.');
    }
};

/**
 * Fetches the detailed information for a single model.
 * @param {string} source - The source of the model (e.g., 'huggingface').
 * @param {string} modelId - The unique identifier of the model.
 * @returns {Promise<ModelDetails>} A promise that resolves to the detailed model information.
 * @throws Will throw a standardized error from handleApiError.
 */
export const getModelDetails = async (source: string, modelId: string): Promise<ModelDetails> => {
    try {
        // URL components must be encoded to handle special characters like '/' in the modelId.
        const response = await apiClient.get<ModelDetails>(
            `/models/${encodeURIComponent(source)}/${encodeURIComponent(modelId)}`,
        );
        return response.data;
    } catch (error) {
        console.error('Error in getModelDetails:', error);
        throw handleApiError(error, 'Failed to fetch model details.');
    }
};

// frontend/src/api/errorHandler.ts
import { AxiosError } from 'axios';

/**
 * @interface BackendErrorDetail
 * Defines the expected structure of a detailed error message from the FastAPI backend.
 * This corresponds to the `detail` field in the HTTPException.
 */
interface BackendErrorDetail {
    detail: string;
}

/**
 * A centralized utility for parsing errors returned from the application's API.
 * It checks for the specific error structure sent by the backend (`{ detail: "..." }`)
 * and creates a clean, readable error message. If the specific structure is not found,
 * it falls back to a generic message or the original error.
 *
 * @param {any} error - The raw error object caught in a try...catch block, expected to be an AxiosError.
 * @param {string} [genericMessage='An unknown error occurred.'] - A fallback message if no specific detail is found.
 * @returns {Error} A new Error object with a user-friendly message.
 */
export const handleApiError = (
    error: any,
    genericMessage: string = 'An unknown error occurred.',
): Error => {
    // Check if the error is an AxiosError and has the expected response structure.
    if (
        error &&
        typeof error === 'object' &&
        'isAxiosError' in error &&
        error.isAxiosError === true
    ) {
        const axiosError = error as AxiosError<BackendErrorDetail>;
        // Check if the response data and the 'detail' property exist.
        if (axiosError.response?.data?.detail) {
            // Return a new Error with the specific message from the backend.
            return new Error(axiosError.response.data.detail);
        }
    }

    // If the error is not in the expected format, return a new Error with the generic message.
    return new Error(genericMessage);
};

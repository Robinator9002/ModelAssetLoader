// frontend/src/state/modalStore.ts
import { create } from 'zustand';
import { type ModelDetails, type ModelFile } from '../api/api';

/**
 * @interface ModalState
 * Defines the shape of the store responsible for managing the state of
 * all global modals within the application. This centralizes the logic
 * for opening, closing, and providing data to modals, preventing the need
 * to manage this state within the top-level App.tsx component.
 */
interface ModalState {
    // State properties for the Download Modal
    isDownloadModalOpen: boolean;
    modelForDownload: ModelDetails | null;
    specificFileForDownload: ModelFile | null;

    // Actions
    /**
     * @fix {TYPESCRIPT} Corrected the type definition for the function.
     * The previous syntax `| null => void` was invalid. The correct syntax
     * defines the parameters and the return type `void` directly.
     */
    openDownloadModal: (model: ModelDetails, specificFile?: ModelFile) => void;
    closeDownloadModal: () => void;
}

/**
 * `useModalStore` is a custom hook created by Zustand.
 *
 * This store is the single source of truth for the state of global modals.
 * Any component can now trigger a modal to open or close by calling the
 * actions from this store, without needing any props passed down from parent
 * components. This significantly decouples components like ModelSearchPage and
 * ModelDetailsPage from App.tsx.
 */
export const useModalStore = create<ModalState>((set) => ({
    // --- INITIAL STATE ---
    isDownloadModalOpen: false,
    modelForDownload: null,
    specificFileForDownload: null,

    // --- ACTIONS ---

    /**
     * Opens the download modal and sets the necessary model data.
     * @param {ModelDetails} model - The full model details object.
     * @param {ModelFile} [specificFile] - An optional specific file to pre-select.
     */
    openDownloadModal: (model: ModelDetails, specificFile?: ModelFile) => {
        set({
            isDownloadModalOpen: true,
            modelForDownload: model,
            specificFileForDownload: specificFile || null,
        });
    },

    /**
     * Closes the download modal and clears its associated data.
     */
    closeDownloadModal: () => {
        set({
            isDownloadModalOpen: false,
            modelForDownload: null,
            specificFileForDownload: null,
        });
    },
}));

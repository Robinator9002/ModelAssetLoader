// frontend/src/components/FileManager/ViewModeSwitcher.tsx
import React from 'react';
import { LayoutGrid, ListTree } from 'lucide-react';

export type ViewMode = 'models' | 'explorer';

interface ViewModeSwitcherProps {
    currentMode: ViewMode;
    onModeChange: (mode: ViewMode) => void;
}

const ViewModeSwitcher: React.FC<ViewModeSwitcherProps> = ({ currentMode, onModeChange }) => {
    return (
        <div className="view-mode-switcher" role="radiogroup">
            <button
                className={`switcher-button ${currentMode === 'models' ? 'active' : ''}`}
                onClick={() => onModeChange('models')}
                aria-checked={currentMode === 'models'}
                role="radio"
                title="Models View"
            >
                <LayoutGrid size={16} />
                <span>Models</span>
            </button>
            <button
                className={`switcher-button ${currentMode === 'explorer' ? 'active' : ''}`}
                onClick={() => onModeChange('explorer')}
                aria-checked={currentMode === 'explorer'}
                role="radio"
                title="Explorer View"
            >
                <ListTree size={16} />
                <span>Explorer</span>
            </button>
        </div>
    );
};

export default ViewModeSwitcher;

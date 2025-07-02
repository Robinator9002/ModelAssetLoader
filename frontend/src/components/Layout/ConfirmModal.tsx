// frontend/src/components/Layout/ConfirmModal.tsx
import React, { useEffect, useState } from "react";
import { AlertTriangle, HelpCircle, CheckCircle, Loader2 } from "lucide-react";

interface ConfirmModalProps {
	isOpen: boolean;
	title: string;
	message: string | React.ReactNode;
	onConfirm: () => Promise<{ message?: string } | void> | void;
	onCancel: () => void;
	confirmText?: string;
	cancelText?: string;
	isDanger?: boolean;
}

const ConfirmModal: React.FC<ConfirmModalProps> = ({
	isOpen,
	title,
	message,
	onConfirm,
	onCancel,
	confirmText = "Bestätigen",
	cancelText = "Abbrechen",
	isDanger = false,
}) => {
    const [isLoading, setIsLoading] = useState(false);
    const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

    // Reset state when modal is opened or closed
    useEffect(() => {
        if (!isOpen) {
            setTimeout(() => {
                setIsLoading(false);
                setFeedback(null);
            }, 300); // Allow for closing animation
        }
    }, [isOpen]);

    // Handle keyboard shortcuts
	useEffect(() => {
		if (!isOpen) return;
		const handleKeyDown = (e: KeyboardEvent) => {
			if (e.key === "Escape" && !isLoading && !feedback) {
				e.preventDefault();
				onCancel();
			}
		};
		document.addEventListener("keydown", handleKeyDown);
		return () => document.removeEventListener("keydown", handleKeyDown);
	}, [isOpen, onCancel, isLoading, feedback]);

	if (!isOpen) {
		return null;
	}

    const handleConfirmClick = async () => {
        setIsLoading(true);
        setFeedback(null);
        try {
            const result = await onConfirm();
            if (result?.message) {
                setFeedback({ type: "success", message: result.message });
                setTimeout(() => onCancel(), 2000);
            } else {
                onCancel();
            }
        } catch (error: any) {
            const errorMessage = error.message || "Ein unerwarteter Fehler ist aufgetreten.";
            setFeedback({ type: "error", message: errorMessage });
            setTimeout(() => {
                setIsLoading(false);
                setFeedback(null);
            }, 2500);
        }
    };
    
    const Icon = isDanger ? AlertTriangle : HelpCircle;
    const isInteractive = !isLoading && !feedback;

	return (
		<div
			className={`modal-overlay confirm-modal-overlay ${isOpen ? "active" : ""}`}
			onClick={isInteractive ? onCancel : undefined}
			role="dialog"
			aria-modal="true"
			aria-labelledby="confirm-modal-title"
		>
			<div
				className="modal-content confirm-modal-content"
				onClick={(e) => e.stopPropagation()}
			>
                {feedback ? (
                    <div className="modal-body confirm-feedback-view">
                        {feedback.type === 'success' ? (
                            <CheckCircle size={48} className="confirm-icon icon-success" />
                        ) : (
                            <AlertTriangle size={48} className="confirm-icon icon-danger" />
                        )}
                        <p>{feedback.message}</p>
                    </div>
                ) : (
                    <>
                        <div className="modal-body confirm-modal-body">
                            <div className="confirm-icon-wrapper">
                                <Icon size={48} className={`confirm-icon ${isDanger ? 'icon-danger' : 'icon-primary'}`} />
                            </div>
                            <h3 id="confirm-modal-title" className="confirm-title">
                                {title}
                            </h3>
                            <p id="confirm-modal-message" className="confirm-message">
                                {message}
                            </p>
                        </div>

                        <div className="modal-actions">
                            <button
                                className="button"
                                onClick={onCancel}
                                disabled={!isInteractive}
                            >
                                {cancelText}
                            </button>
                            <button
                                className={`button ${isDanger ? "button-danger" : "button-primary"}`}
                                onClick={handleConfirmClick}
                                disabled={!isInteractive}
                            >
                                {isLoading ? <Loader2 size={18} className="animate-spin" /> : confirmText}
                            </button>
                        </div>
                    </>
                )}
			</div>
		</div>
	);
};

export default ConfirmModal;

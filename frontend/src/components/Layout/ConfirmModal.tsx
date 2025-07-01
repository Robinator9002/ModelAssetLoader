// frontend/src/components/Layout/ConfirmModal.tsx
import React, { useEffect } from "react";
import { AlertTriangle, HelpCircle } from "lucide-react";

interface ConfirmModalProps {
	isOpen: boolean;
	title: string;
	message: string | React.ReactNode;
	onConfirm: () => void;
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
	confirmText = "Confirm",
	cancelText = "Cancel",
	isDanger = false,
}) => {
	useEffect(() => {
		if (!isOpen) return;

		const handleKeyDown = (e: KeyboardEvent) => {
			if (e.key === "Enter" && !isDanger) {
				e.preventDefault();
				onConfirm();
			}
			if (e.key === "Escape") {
				e.preventDefault();
				onCancel();
			}
		};

		document.addEventListener("keydown", handleKeyDown);
		return () => {
			document.removeEventListener("keydown", handleKeyDown);
		};
	}, [isOpen, onConfirm, onCancel, isDanger]);

	if (!isOpen) {
		return null;
	}
    
    const Icon = isDanger ? AlertTriangle : HelpCircle;

	return (
		<div
			className={`modal-overlay confirm-modal-overlay ${isOpen ? "active" : ""}`}
			onClick={onCancel}
			role="dialog"
			aria-modal="true"
			aria-labelledby="confirm-modal-title"
			aria-describedby="confirm-modal-message"
		>
			<div
				className={`modal-content confirm-modal-content ${isDanger ? "modal-danger" : ""}`}
				onClick={(e) => e.stopPropagation()}
			>
                <div className="confirm-modal-icon-area">
                    <Icon size={48} className={`confirm-icon ${isDanger ? 'icon-danger' : 'icon-primary'}`} />
                </div>
				
                <div className="confirm-modal-text-content">
                    <h3 id="confirm-modal-title" className="confirm-modal-title">
                        {title}
                    </h3>
                    <div id="confirm-modal-message" className="confirm-modal-message">
                        {message}
                    </div>
                </div>

				<div className="modal-actions confirm-modal-actions">
					<button
						className="button"
						onClick={onCancel}
					>
						{cancelText}
					</button>
					<button
						className={`button ${isDanger ? "button-danger" : "button-primary"}`}
						onClick={onConfirm}
					>
						{confirmText}
					</button>
				</div>
			</div>
		</div>
	);
};

export default ConfirmModal;

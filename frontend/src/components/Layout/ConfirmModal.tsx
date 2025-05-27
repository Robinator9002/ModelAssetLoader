// frontend/src/components/Layout/ConfirmModal.tsx
import React, { useEffect } from "react";
// CSS wird global importiert: @import url('../../style/Layout/ConfirmModal.css');

interface ConfirmModalProps {
	isOpen: boolean;
	title?: string;
	message: string | React.ReactNode; // Erlaube auch JSX für die Nachricht
	onConfirm: () => void;
	onCancel: () => void;
	confirmText?: string;
	cancelText?: string;
	isDanger?: boolean; // Für "gefährliche" Aktionen (z.B. Löschen)
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
	useEffect(() => {
		if (!isOpen) return;

		const handleKeyDown = (e: KeyboardEvent) => {
			if (e.key === "Enter" && !isDanger) {
				// Enter nur bei nicht-gefährlichen Aktionen
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

	return (
		<div
			className={`modal-overlay confirm-modal-overlay ${
				isOpen ? "active" : ""
			}`}
			onClick={onCancel} // Klick auf Overlay schließt Modal
			role="dialog"
			aria-modal="true"
			aria-labelledby={title ? "confirm-modal-title" : undefined}
			aria-describedby="confirm-modal-message"
		>
			<div
				className={`modal-content confirm-modal-content ${
					isDanger ? "modal-danger" : ""
				}`}
				onClick={(e) => e.stopPropagation()} // Verhindert Schließen bei Klick in Modal-Content
			>
				{title && (
					<h3 id="confirm-modal-title" className="confirm-modal-title">
						{title}
					</h3>
				)}
				<div id="confirm-modal-message" className="confirm-modal-message">
					{message}
				</div>
				<div className="confirm-modal-actions">
					<button
						className="button modal-button cancel-button" // Standard Button-Klasse + spezifische
						onClick={onCancel}
					>
						{cancelText}
					</button>
					<button
						className={`button modal-button confirm-button ${
							isDanger ? "button-danger" : "button-primary-alt"
						}`} // button-primary-alt für weniger Dominanz
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

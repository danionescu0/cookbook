import { useEffect, useRef } from "react";
import { dangerButtonSolid, secondaryButton } from "./buttonStyles";

interface ConfirmDialogProps {
  message: string;
  confirmLabel: string;
  cancelLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
}

// Generic yes/no overlay for a destructive action — see ui/useConfirm.tsx for the imperative
// confirm(message) API call sites actually use instead of rendering this directly.
export function ConfirmDialog({
  message,
  confirmLabel,
  cancelLabel,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  // Cancel gets initial focus, not Confirm — an accidental Enter press should never be the thing
  // that deletes something.
  const cancelButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    cancelButtonRef.current?.focus();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [onCancel]);

  return (
    <div
      role="presentation"
      onClick={onCancel}
      className="motion-safe-dialog-animation fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4 backdrop-blur-sm"
      style={{ animation: "dialog-backdrop-in 150ms ease-out" }}
    >
      <div
        role="alertdialog"
        aria-modal="true"
        aria-describedby="confirm-dialog-message"
        onClick={(event) => event.stopPropagation()}
        className="motion-safe-dialog-animation w-full max-w-sm rounded-lg bg-cream-card p-6 text-center shadow-xl ring-1 ring-black/5"
        style={{ animation: "dialog-panel-in 180ms ease-out" }}
      >
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-50 ring-1 ring-red-100">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="h-6 w-6 text-red-600"
            aria-hidden="true"
          >
            <path d="M4 7h16" />
            <path d="M9 7V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v3" />
            <path d="M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12" />
            <path d="M10 11v6" />
            <path d="M14 11v6" />
          </svg>
        </div>

        <p id="confirm-dialog-message" className="mt-4 text-base text-ink">
          {message}
        </p>

        <div className="mt-6 flex justify-center gap-3">
          <button type="button" ref={cancelButtonRef} onClick={onCancel} className={secondaryButton}>
            {cancelLabel}
          </button>
          <button type="button" onClick={onConfirm} className={dangerButtonSolid}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

import { useCallback, useState } from "react";
import { createPortal } from "react-dom";
import { useLanguage } from "../i18n/LanguageContext";
import { ConfirmDialog } from "./ConfirmDialog";

interface PendingConfirm {
  message: string;
  confirmLabel: string;
  resolve: (value: boolean) => void;
}

// Drop-in async replacement for `window.confirm(message)` (`if (!(await confirm(...))) return;`)
// that renders a styled overlay instead of the native browser dialog. Render the returned
// `confirmDialog` node once, anywhere in the calling component's tree (a portal, so placement
// doesn't affect layout).
export function useConfirm() {
  const { t } = useLanguage();
  const [pending, setPending] = useState<PendingConfirm | null>(null);

  // confirmLabel defaults to "Delete" — every call site so far has been a delete confirmation;
  // pass an explicit label (e.g. t.recipeManager.reparse) for anything else, so the button never
  // says "Delete" for an action that isn't one.
  const confirm = useCallback(
    (message: string, confirmLabel?: string) => {
      return new Promise<boolean>((resolve) => {
        setPending({ message, confirmLabel: confirmLabel ?? t.common.delete, resolve });
      });
    },
    [t]
  );

  const respond = (value: boolean) => {
    pending?.resolve(value);
    setPending(null);
  };

  const confirmDialog = pending
    ? createPortal(
        <ConfirmDialog
          message={pending.message}
          confirmLabel={pending.confirmLabel}
          cancelLabel={t.common.cancel}
          onConfirm={() => respond(true)}
          onCancel={() => respond(false)}
        />,
        document.body
      )
    : null;

  return { confirm, confirmDialog };
}

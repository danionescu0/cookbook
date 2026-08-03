import { useCallback, useState } from "react";
import { createPortal } from "react-dom";
import { useLanguage } from "../i18n/LanguageContext";
import { ConfirmDialog } from "./ConfirmDialog";

interface PendingConfirm {
  message: string;
  resolve: (value: boolean) => void;
}

// Drop-in async replacement for `window.confirm(message)` (`if (!(await confirm(...))) return;`)
// that renders a styled overlay instead of the native browser dialog. Render the returned
// `confirmDialog` node once, anywhere in the calling component's tree (a portal, so placement
// doesn't affect layout).
export function useConfirm() {
  const { t } = useLanguage();
  const [pending, setPending] = useState<PendingConfirm | null>(null);

  const confirm = useCallback((message: string) => {
    return new Promise<boolean>((resolve) => {
      setPending({ message, resolve });
    });
  }, []);

  const respond = (value: boolean) => {
    pending?.resolve(value);
    setPending(null);
  };

  const confirmDialog = pending
    ? createPortal(
        <ConfirmDialog
          message={pending.message}
          confirmLabel={t.common.delete}
          cancelLabel={t.common.cancel}
          onConfirm={() => respond(true)}
          onCancel={() => respond(false)}
        />,
        document.body
      )
    : null;

  return { confirm, confirmDialog };
}

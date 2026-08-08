import { useEffect } from "react";
import { useLanguage } from "../i18n/LanguageContext";
import { primaryButton } from "../ui/buttonStyles";

interface HowToImportBookmarksDialogProps {
  onClose: () => void;
}

// Same overlay shape as legal/TermsOverlay.tsx (fixed backdrop, scrollable body, Escape to
// close, body scroll locked while open) but simpler: no scroll-to-agree gating, just an OK
// button that's always enabled — this is instructions, not a consent flow.
export function HowToImportBookmarksDialog({ onClose }: HowToImportBookmarksDialogProps) {
  const { t } = useLanguage();

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [onClose]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="how-to-import-heading"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
    >
      <div className="flex max-h-[85vh] w-full max-w-xl flex-col rounded-lg bg-cream-card ring-1 ring-black/5">
        <div className="border-b border-olive-light px-6 py-4">
          <h2 id="how-to-import-heading" className="font-serif text-xl font-semibold text-ink">
            {t.howToImportBookmarks.title}
          </h2>
        </div>

        <div className="flex-1 space-y-6 overflow-y-auto px-6 py-4 text-sm leading-relaxed text-ink/80">
          {t.howToImportBookmarks.sections.map((section) => (
            <section key={section.heading}>
              <h3 className="font-serif text-base font-semibold text-ink">{section.heading}</h3>
              <ol className="mt-2 list-decimal space-y-1 pl-5">
                {section.body.map((step, index) => (
                  <li key={index}>{step}</li>
                ))}
              </ol>
            </section>
          ))}
        </div>

        <div className="border-t border-olive-light px-6 py-4 text-center">
          <button type="button" onClick={onClose} className={primaryButton}>
            {t.howToImportBookmarks.closeButton}
          </button>
        </div>
      </div>
    </div>
  );
}

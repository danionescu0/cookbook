import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useLanguage } from "../i18n/LanguageContext";
import { primaryButton } from "../ui/buttonStyles";
import { TermsContent } from "./TermsContent";

interface TermsOverlayProps {
  onAgree: () => void;
  onClose: () => void;
}

// A near-bottom threshold rather than an exact one — fonts/zoom can leave a stray sub-pixel gap
// that would otherwise never register as "reached the end."
const SCROLL_END_THRESHOLD_PX = 8;

export function TermsOverlay({ onAgree, onClose }: TermsOverlayProps) {
  const { t } = useLanguage();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [scrolledToEnd, setScrolledToEnd] = useState(false);

  const checkScrolledToEnd = () => {
    const el = scrollRef.current;
    if (!el) return;
    if (el.scrollHeight - el.scrollTop - el.clientHeight <= SCROLL_END_THRESHOLD_PX) {
      setScrolledToEnd(true);
    }
  };

  // Content short enough to fit without scrolling shouldn't block on a scroll gesture that has
  // nowhere to go.
  useLayoutEffect(() => {
    checkScrolledToEnd();
  }, []);

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
      aria-labelledby="terms-overlay-heading"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
    >
      <div className="flex max-h-[85vh] w-full max-w-xl flex-col rounded-lg bg-cream-card ring-1 ring-black/5">
        <div className="flex items-center justify-between border-b border-olive-light px-6 py-4">
          <h2 id="terms-overlay-heading" className="font-serif text-xl font-semibold text-ink">
            {t.terms.title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={t.terms.closeButton}
            className="rounded-md px-2 py-1 text-ink/50 hover:bg-olive-light hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-terracotta"
          >
            ✕
          </button>
        </div>

        <div
          ref={scrollRef}
          onScroll={checkScrolledToEnd}
          data-testid="terms-scroll-container"
          className="flex-1 overflow-y-auto px-6 py-4"
        >
          <TermsContent />
        </div>

        <div className="border-t border-olive-light px-6 py-4 text-center">
          {scrolledToEnd ? (
            <button type="button" onClick={onAgree} className={primaryButton}>
              {t.terms.agreeButton}
            </button>
          ) : (
            <p role="status" className="text-sm text-ink/60">
              {t.terms.scrollHint}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

import { useLanguage } from "../i18n/LanguageContext";
import { TermsContent } from "./TermsContent";

// Reachable at /terms regardless of login state — the static reference copy of the same text
// shown inside the signup overlay (TermsOverlay).
export function TermsPage() {
  const { t } = useLanguage();

  return (
    <section className="mx-auto max-w-2xl rounded-lg bg-cream-card p-6 ring-1 ring-black/5">
      <h2 className="font-serif text-2xl font-semibold text-ink">{t.terms.title}</h2>
      <div className="mt-4">
        <TermsContent />
      </div>
    </section>
  );
}

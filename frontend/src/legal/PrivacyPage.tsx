import { useLanguage } from "../i18n/LanguageContext";
import { PrivacyContent } from "./PrivacyContent";

// Reachable at /privacy regardless of login state — required as a public URL for Google's OAuth
// consent screen (see TermsPage's own docstring for the same reasoning).
export function PrivacyPage() {
  const { t } = useLanguage();

  return (
    <section className="mx-auto max-w-2xl rounded-lg bg-cream-card p-6 ring-1 ring-black/5">
      <h2 className="font-serif text-2xl font-semibold text-ink">{t.privacy.title}</h2>
      <div className="mt-4">
        <PrivacyContent />
      </div>
    </section>
  );
}

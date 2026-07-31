import { useLanguage } from "../i18n/LanguageContext";

// Shared by TermsPage (the static, standalone page) and TermsOverlay (the scroll-to-accept
// modal shown during signup) so the two always show exactly the same text.
export function TermsContent() {
  const { t } = useLanguage();

  return (
    <article className="space-y-6 text-sm leading-relaxed text-ink/80">
      <p className="text-xs text-ink/50">{t.terms.lastUpdated}</p>
      {t.terms.sections.map((section) => (
        <section key={section.heading}>
          <h3 className="font-serif text-base font-semibold text-ink">{section.heading}</h3>
          {section.body.map((paragraph, index) => (
            <p key={index} className="mt-2">
              {paragraph}
            </p>
          ))}
        </section>
      ))}
    </article>
  );
}

import { useLanguage } from "../i18n/LanguageContext";

// Mirrors TermsContent's structure — same t.privacy.sections shape as t.terms.sections.
export function PrivacyContent() {
  const { t } = useLanguage();

  return (
    <article className="space-y-6 text-sm leading-relaxed text-ink/80">
      <p className="text-xs text-ink/50">{t.privacy.lastUpdated}</p>
      {t.privacy.sections.map((section) => (
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

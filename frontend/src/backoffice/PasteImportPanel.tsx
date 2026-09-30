import { useState } from "react";
import { api } from "../api/client";
import { useLanguage } from "../i18n/LanguageContext";
import { primaryButton } from "../ui/buttonStyles";

// Same minimum as the api's own defense-in-depth check (routers/imports.py's
// _MIN_PASTE_TEXT_LENGTH) — kept in sync by hand, matching the "Worker/API code sharing"
// design decision already used elsewhere in this app.
const MIN_TEXT_LENGTH = 30;

interface PasteImportPanelProps {
  // Same hand-off as ImportManager's/BookmarkImportPanel's own onJobCreated — see
  // ImportManager's docstring. The created job appears in ImportManager's own in-progress list
  // automatically (it lists every import job regardless of type), so this panel doesn't need its
  // own progress list.
  onJobCreated?: () => void;
}

export function PasteImportPanel({ onJobCreated }: PasteImportPanelProps) {
  const { t } = useLanguage();
  const [text, setText] = useState("");
  // Single flag, mirroring the api's one `enrich_from_web` field: opting in makes the worker do
  // one extra web-search call before extraction, used both to fill gaps in the pasted text and
  // to propose photos — see worker/app/claude_client.py's research_recipe_context. Kept as one
  // checkbox rather than two, since a second checkbox would imply an independent knob that the
  // API doesn't actually have.
  const [enrichFromWeb, setEnrichFromWeb] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const tooShort = text.trim().length > 0 && text.trim().length < MIN_TEXT_LENGTH;
  const canSubmit = text.trim().length >= MIN_TEXT_LENGTH && !submitting;

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!canSubmit) return;
    setError(null);
    setSubmitting(true);
    try {
      await api.createTextImportJob(text.trim(), enrichFromWeb);
      setText("");
      setEnrichFromWeb(false);
      onJobCreated?.();
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mt-6 border-t border-olive-light pt-4">
      <h3 className="font-serif text-lg font-semibold text-ink">{t.pasteImport.heading}</h3>
      <p className="mt-1 text-sm text-ink/60">{t.pasteImport.description}</p>

      <form onSubmit={handleSubmit} className="mt-3 flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <label htmlFor="paste-import-text" className="text-sm font-medium text-ink/70">
            {t.pasteImport.textLabel}
          </label>
          <textarea
            id="paste-import-text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={6}
            placeholder={t.pasteImport.placeholder}
            className="rounded-md border border-olive/30 bg-white px-3 py-2 text-sm text-ink focus:border-terracotta focus:outline-none"
          />
          {tooShort && <p className="text-sm text-ink/60">{t.pasteImport.tooShortHint}</p>}
        </div>

        <label className="flex items-center gap-2 text-sm text-ink/70">
          <input
            type="checkbox"
            checked={enrichFromWeb}
            onChange={(e) => setEnrichFromWeb(e.target.checked)}
          />
          {t.pasteImport.enrichFromWebLabel}
        </label>

        <div>
          <button type="submit" disabled={!canSubmit} className={primaryButton}>
            {t.pasteImport.submitButton}
          </button>
        </div>
      </form>

      {error && (
        <p role="alert" className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}
    </div>
  );
}

import { useRef, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useLanguage } from "../i18n/LanguageContext";
import { primaryButton, secondaryButton } from "../ui/buttonStyles";
import { HowToImportBookmarksDialog } from "./HowToImportBookmarksDialog";
import type { BookmarkLink } from "../types";

interface BookmarkImportPanelProps {
  // Same hand-off as ImportManager's own onJobCreated — see that component's docstring. Bulk
  // bookmark imports can start several jobs at once, so this fires once after the whole batch,
  // not per job.
  onJobCreated?: () => void;
}

type Stage = "idle" | "parsing" | "selecting" | "importing" | "done";

export function BookmarkImportPanel({ onJobCreated }: BookmarkImportPanelProps) {
  const { t } = useLanguage();
  const { user } = useAuth();
  const isAdmin = user?.is_admin ?? false;
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [stage, setStage] = useState<Stage>("idle");
  const [links, setLinks] = useState<BookmarkLink[]>([]);
  const [remainingQuota, setRemainingQuota] = useState<number | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ created: number; skipped: number } | null>(null);
  const [showHowTo, setShowHowTo] = useState(false);

  const reset = () => {
    setStage("idle");
    setLinks([]);
    setRemainingQuota(null);
    setSelected(new Set());
    setError(null);
    setResult(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleFileChosen = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setError(null);
    setStage("parsing");
    try {
      const parsed = await api.parseBookmarkFile(file);
      setLinks(parsed.links);
      setRemainingQuota(parsed.remaining_quota);
      setSelected(new Set());
      setStage("selecting");
    } catch (e) {
      setError(String(e));
      setStage("idle");
    }
  };

  const atSelectionCap = remainingQuota !== null && selected.size >= remainingQuota;

  const toggleLink = (url: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(url)) {
        next.delete(url);
      } else if (!atSelectionCap) {
        next.add(url);
      }
      return next;
    });
  };

  const handleImportSelected = async () => {
    if (selected.size === 0) return;
    setError(null);
    setStage("importing");
    try {
      const outcome = await api.importBookmarkSelection([...selected]);
      setResult({ created: outcome.created.length, skipped: outcome.skipped_duplicate.length });
      setStage("done");
      if (outcome.created.length > 0) onJobCreated?.();
    } catch (e) {
      setError(String(e));
      setStage("selecting");
    }
  };

  return (
    <div className="mt-6 border-t border-olive-light pt-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-serif text-lg font-semibold text-ink">{t.bookmarkImport.heading}</h3>
        <button
          type="button"
          onClick={() => setShowHowTo(true)}
          className="text-sm text-terracotta hover:underline"
        >
          {t.bookmarkImport.howToImportLink}
        </button>
      </div>
      <p className="mt-1 text-sm text-ink/60">{t.bookmarkImport.description}</p>

      {stage === "idle" && (
        <>
          <input
            ref={fileInputRef}
            type="file"
            accept=".html,.htm"
            onChange={handleFileChosen}
            className="sr-only"
            id="bookmark-file-input"
          />
          <label htmlFor="bookmark-file-input" className={`${secondaryButton} mt-3 inline-block cursor-pointer`}>
            {t.bookmarkImport.loadFileButton}
          </label>
        </>
      )}

      {stage === "parsing" && <p className="mt-3 text-sm text-ink/60">{t.bookmarkImport.parsing}</p>}

      {stage === "selecting" && (
        <div className="mt-3">
          {links.length === 0 ? (
            <p className="text-sm text-ink/60">{t.bookmarkImport.noLinksFound}</p>
          ) : (
            <>
              <p className="text-sm text-ink/70">
                {t.bookmarkImport.linksFoundHeading.replace("{count}", String(links.length))}
              </p>
              {!isAdmin && remainingQuota !== null && (
                <p className={`mt-1 text-sm ${atSelectionCap ? "font-medium text-terracotta" : "text-ink/60"}`}>
                  {t.bookmarkImport.selectionCount
                    .replace("{selected}", String(selected.size))
                    .replace("{limit}", String(remainingQuota))}
                </p>
              )}
              <ul className="mt-2 max-h-80 divide-y divide-olive-light overflow-y-auto rounded-md border border-olive/20">
                {links.map((link) => {
                  const disabled = link.already_imported || (!selected.has(link.url) && atSelectionCap);
                  return (
                    <li key={link.url} className="flex items-center gap-2 px-3 py-2">
                      <input
                        type="checkbox"
                        id={`bookmark-link-${link.url}`}
                        checked={selected.has(link.url)}
                        disabled={disabled}
                        onChange={() => toggleLink(link.url)}
                      />
                      <label
                        htmlFor={`bookmark-link-${link.url}`}
                        className={`min-w-0 flex-1 text-sm ${disabled ? "text-ink/40" : "text-ink"}`}
                      >
                        <span className="block truncate">{link.title}</span>
                        <span className="block truncate text-xs text-ink/50">{link.url}</span>
                      </label>
                      {link.already_imported && (
                        <span className="shrink-0 text-xs text-ink/50">
                          {t.bookmarkImport.alreadyImportedBadge}
                        </span>
                      )}
                    </li>
                  );
                })}
              </ul>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={handleImportSelected}
                  disabled={selected.size === 0}
                  className={primaryButton}
                >
                  {t.bookmarkImport.importSelectedButton}
                </button>
                <button type="button" onClick={reset} className={secondaryButton}>
                  {t.bookmarkImport.chooseAnotherFileButton}
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {stage === "importing" && (
        <p className="mt-3 text-sm text-ink/60">{t.bookmarkImport.importing}</p>
      )}

      {stage === "done" && result && (
        <div className="mt-3">
          <p role="status" className="text-sm text-ink">
            {result.skipped > 0
              ? t.bookmarkImport.resultSummary
                  .replace("{created}", String(result.created))
                  .replace("{skipped}", String(result.skipped))
              : t.bookmarkImport.resultSummaryNoSkipped.replace("{created}", String(result.created))}
          </p>
          <button type="button" onClick={reset} className={`${secondaryButton} mt-2`}>
            {t.bookmarkImport.chooseAnotherFileButton}
          </button>
        </div>
      )}

      {error && (
        <p role="alert" className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {showHowTo && <HowToImportBookmarksDialog onClose={() => setShowHowTo(false)} />}
    </div>
  );
}

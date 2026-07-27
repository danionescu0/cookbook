import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useLanguage } from "../i18n/LanguageContext";
import { primaryButton } from "../ui/buttonStyles";
import type { IngredientRefreshState } from "../types";

const ACTIVE: IngredientRefreshState[] = ["queued", "processing"];

export function IngredientRefreshPanel() {
  const { t } = useLanguage();
  const [status, setStatus] = useState<IngredientRefreshState | null>(null);
  const [jobError, setJobError] = useState<string | null>(null);
  const [updatedCount, setUpdatedCount] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const reload = () =>
    api
      .getIngredientRefreshStatus()
      .then((result) => {
        setStatus(result.status);
        setJobError(result.error);
        setUpdatedCount(result.ingredients_updated);
      })
      .catch((e) => setActionError(String(e)));

  useEffect(() => {
    reload();
  }, []);

  // Poll only while a refresh is actually in flight — same pattern as ImportManager/RecipeManager.
  useEffect(() => {
    if (!status || !ACTIVE.includes(status)) return;
    const interval = setInterval(reload, 3000);
    return () => clearInterval(interval);
  }, [status]);

  const handleRefresh = async () => {
    setActionError(null);
    try {
      const job = await api.createIngredientRefreshJob();
      setStatus(job.status);
      setJobError(job.error);
      setUpdatedCount(job.ingredients_updated);
    } catch (e) {
      setActionError(String(e));
    }
  };

  const isActive = status !== null && ACTIVE.includes(status);

  return (
    <section
      aria-labelledby="ingredient-refresh-heading"
      className="rounded-lg bg-cream-card p-5 ring-1 ring-black/5"
    >
      <h2 id="ingredient-refresh-heading" className="font-serif text-2xl font-semibold text-ink">
        {t.ingredientRefresh.heading}
      </h2>
      <p className="mt-1 text-sm text-ink/60">{t.ingredientRefresh.description}</p>

      <button
        type="button"
        onClick={handleRefresh}
        disabled={isActive}
        className={`mt-4 ${primaryButton}`}
      >
        {isActive ? t.ingredientRefresh.buttonBusy : t.ingredientRefresh.button}
      </button>

      {status && (
        <p className="mt-3 text-sm text-ink/70">
          {t.ingredientRefresh.statuses[status]}
          {status === "done" &&
            updatedCount !== null &&
            ` — ${t.ingredientRefresh.updatedCount.replace("{count}", String(updatedCount))}`}
        </p>
      )}
      {status === "failed" && jobError && (
        <p role="alert" className="mt-1 text-sm text-red-700">
          {jobError}
        </p>
      )}
      {actionError && (
        <p role="alert" className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {actionError}
        </p>
      )}
    </section>
  );
}

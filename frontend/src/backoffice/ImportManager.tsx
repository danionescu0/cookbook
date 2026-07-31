import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useLanguage } from "../i18n/LanguageContext";
import { dangerButton, primaryButton } from "../ui/buttonStyles";
import type { Category, ImportJob, ImportJobStatus } from "../types";

const ACTIVE: ImportJobStatus[] = ["queued", "fetching", "processing"];

export function ImportManager() {
  const { t } = useLanguage();
  const [categories, setCategories] = useState<Category[]>([]);
  const [jobs, setJobs] = useState<ImportJob[]>([]);
  const [source, setSource] = useState("");
  const [categoryId, setCategoryId] = useState<number | "">("");
  const [error, setError] = useState<string | null>(null);

  const reload = () => api.listImportJobs().then(setJobs).catch((e) => setError(String(e)));

  useEffect(() => {
    api.listCategories().then(setCategories).catch((e) => setError(String(e)));
    reload();
  }, []);

  // Poll while any job is mid-flight — jobs only progress via the worker in the background, not
  // through any action here, so this is the only way the list picks up done/failed transitions.
  useEffect(() => {
    if (!jobs.some((job) => ACTIVE.includes(job.status))) return;
    const interval = setInterval(reload, 3000);
    return () => clearInterval(interval);
  }, [jobs]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!source.trim() || categoryId === "") return;
    setError(null);
    try {
      await api.createImportJob(source.trim(), categoryId);
      setSource("");
      await reload();
    } catch (e) {
      setError(String(e));
    }
  };

  const handleApprove = async (id: number) => {
    setError(null);
    try {
      await api.approveImportJob(id);
      await reload();
    } catch (e) {
      setError(String(e));
    }
  };

  const handleDelete = async (id: number) => {
    setError(null);
    try {
      await api.deleteImportJob(id);
      await reload();
    } catch (e) {
      setError(String(e));
    }
  };

  // A "done" job's data now lives entirely on the Recipe it produced (source_url, etc, see
  // RecipeManager) — it drops out of this list the moment it finishes rather than appearing
  // twice. `jobs` itself (unfiltered) still drives the polling effect above.
  const inProgressJobs = jobs.filter((job) => job.status !== "done");

  return (
    <div className="mt-4">
      <h3 className="font-serif text-lg font-semibold text-ink">{t.importManager.heading}</h3>
      <p className="mt-1 text-sm text-ink/60">{t.importManager.instagramHint}</p>
      <p className="mt-1 text-sm text-ink/60">{t.importManager.privateHint}</p>

      <form onSubmit={handleSubmit} className="mt-4 flex flex-wrap items-end gap-3">
        <div className="flex min-w-64 flex-1 flex-col gap-1">
          <label htmlFor="import-url" className="text-sm font-medium text-ink/70">
            {t.importManager.urlLabel}
          </label>
          <input
            id="import-url"
            value={source}
            onChange={(e) => setSource(e.target.value)}
            placeholder="https://example.com/some-recipe"
            className="rounded-md border border-olive/30 bg-white px-3 py-2 text-sm text-ink focus:border-terracotta focus:outline-none"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="import-category" className="text-sm font-medium text-ink/70">
            {t.importManager.categoryLabel}
          </label>
          <select
            id="import-category"
            value={categoryId}
            onChange={(e) => setCategoryId(e.target.value ? Number(e.target.value) : "")}
            className="rounded-md border border-olive/30 bg-white px-3 py-2 text-sm text-ink focus:border-terracotta focus:outline-none"
          >
            <option value="">{t.importManager.categoryPlaceholder}</option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
        </div>

        <button type="submit" className={primaryButton}>
          {t.importManager.add}
        </button>
      </form>

      {error && (
        <p role="alert" className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {inProgressJobs.length > 0 && (
        <>
          <h3 className="mt-6 font-serif text-lg font-semibold text-ink">
            {t.importManager.inProgressHeading}
          </h3>
          <ul className="mt-2 divide-y divide-olive-light">
            {inProgressJobs.map((job) => (
              <li key={job.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
                <div>
                  <p className="break-all text-ink">{job.source}</p>
                  <p className="text-sm text-ink/50">
                    {t.importManager.statuses[job.status]}
                    {job.created_by_username && (
                      <span className="ml-2">
                        {t.importManager.importedBy.replace("{username}", job.created_by_username)}
                      </span>
                    )}
                  </p>
                  {job.error && <p className="text-sm text-red-700">{job.error}</p>}
                </div>
                <div className="flex shrink-0 flex-wrap gap-2">
                  {job.status === "pending" && (
                    <button
                      type="button"
                      onClick={() => handleApprove(job.id)}
                      className={primaryButton}
                    >
                      {t.importManager.runImport}
                    </button>
                  )}
                  {job.status === "failed" && (
                    <button
                      type="button"
                      onClick={() => handleApprove(job.id)}
                      className={primaryButton}
                    >
                      {t.importManager.retry}
                    </button>
                  )}
                  <button type="button" onClick={() => handleDelete(job.id)} className={dangerButton}>
                    {t.importManager.delete}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

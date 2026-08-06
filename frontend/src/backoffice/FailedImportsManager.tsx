import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useLanguage } from "../i18n/LanguageContext";
import { dangerButton, primaryButton, secondaryButton } from "../ui/buttonStyles";
import { hostnameOf } from "../ui/hostnameOf";
import { Pagination } from "../ui/Pagination";
import { useConfirm } from "../ui/useConfirm";
import type { Category, ImportJob } from "../types";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString();
}

// The full history of failed imports, across every user, with the raw error text — unlike
// ImportManager (shared with the account page), which gates that raw text to admins already and
// drops a job the moment its owner dismisses it. This page ignores dismissed_at entirely: an
// owner clearing their own notification must never erase the admin record. Once an admin has
// looked at one, "Mark as reviewed" clears it from this list via its own, independent
// admin_reviewed_at flag — see routers/imports.py's mark_import_reviewed.
export function FailedImportsManager() {
  const { t } = useLanguage();
  const { confirm, confirmDialog } = useConfirm();
  const [categories, setCategories] = useState<Category[]>([]);
  const [jobs, setJobs] = useState<ImportJob[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pageSize, setPageSize] = useState(10);
  const [currentPage, setCurrentPage] = useState(1);
  const [total, setTotal] = useState(0);

  const reload = () =>
    api
      .listFailedImportsPage({ limit: pageSize, offset: (currentPage - 1) * pageSize })
      .then(({ items, total: newTotal }) => {
        setJobs(items);
        setTotal(newTotal);
      })
      .catch((e) => setError(String(e)));

  useEffect(() => {
    api.listCategories().then(setCategories).catch(() => {});
    api
      .getPublicSettings()
      .then((settings) => setPageSize(settings.backoffice_recipes_page_size))
      .catch(() => {});
  }, []);

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentPage, pageSize]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  useEffect(() => {
    if (currentPage > totalPages) setCurrentPage(totalPages);
  }, [currentPage, totalPages]);

  const categoryName = (categoryId: number) =>
    categories.find((c) => c.id === categoryId)?.name ?? categoryId;

  const handleRetry = async (id: number) => {
    setError(null);
    try {
      await api.approveImportJob(id);
      await reload();
    } catch (e) {
      setError(String(e));
    }
  };

  const handleDelete = async (id: number) => {
    if (!(await confirm(t.importManager.confirmDelete))) return;
    setError(null);
    try {
      await api.deleteImportJob(id);
      await reload();
    } catch (e) {
      setError(String(e));
    }
  };

  const handleMarkReviewed = async (id: number) => {
    setError(null);
    try {
      await api.markImportReviewed(id);
      await reload();
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <div className="rounded-lg bg-cream-card p-5 ring-1 ring-black/5">
      <h2 className="font-serif text-2xl font-semibold text-ink">
        {t.failedImportsManager.heading}
      </h2>

      {error && (
        <p role="alert" className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {jobs.length === 0 ? (
        <p className="mt-3 text-sm text-ink/60">{t.failedImportsManager.empty}</p>
      ) : (
        <ul className="mt-4 divide-y divide-olive-light">
          {jobs.map((job) => (
            <li key={job.id} className="py-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <a
                    href={job.source}
                    target="_blank"
                    rel="noreferrer"
                    className="break-all text-ink hover:underline"
                  >
                    {hostnameOf(job.source)}
                  </a>
                  <span className="ml-2 text-sm text-ink/50">{categoryName(job.category_id)}</span>
                  {job.created_by_username && (
                    <span className="ml-2 text-sm text-ink/50">
                      {t.importManager.importedBy.replace("{username}", job.created_by_username)}
                    </span>
                  )}
                  <span className="ml-2 text-sm text-ink/50">{formatDate(job.created_at)}</span>
                  <span className="ml-2 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
                    {job.error_kind === "disallowed"
                      ? t.failedImportsManager.errorKindDisallowed
                      : t.failedImportsManager.errorKindTechnical}
                  </span>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button type="button" onClick={() => handleRetry(job.id)} className={primaryButton}>
                    {t.importManager.retry}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleMarkReviewed(job.id)}
                    className={secondaryButton}
                  >
                    {t.failedImportsManager.markReviewed}
                  </button>
                  <button type="button" onClick={() => handleDelete(job.id)} className={dangerButton}>
                    {t.importManager.delete}
                  </button>
                </div>
              </div>
              {job.error && <p className="mt-1 break-all text-sm text-red-700">{job.error}</p>}
            </li>
          ))}
        </ul>
      )}

      <Pagination
        currentPage={currentPage}
        totalPages={totalPages}
        onPageChange={setCurrentPage}
        ariaLabel={t.recipeManager.paginationLabel}
        previousLabel={t.recipeManager.previousPage}
        nextLabel={t.recipeManager.nextPage}
      />

      {confirmDialog}
    </div>
  );
}

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, BASE_URL } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useLanguage } from "../i18n/LanguageContext";
import { secondaryButton } from "../ui/buttonStyles";
import { hostnameOf } from "../ui/hostnameOf";
import type { Category, ImportJob, ImportJobStatus, Recipe } from "../types";

// Mirrors api's routers/imports.py _INSTAGRAM_HOSTS — used here only to decide whether to show
// the play-button warning, not to detect the job type itself (that's already settled server-side
// by the time a recipe exists).
const INSTAGRAM_HOSTS = new Set(["instagram.com", "www.instagram.com", "instagr.am"]);

function isInstagramImport(recipe: Recipe): boolean {
  return recipe.source_url !== null && INSTAGRAM_HOSTS.has(hostnameOf(recipe.source_url));
}

const ACTIVE: ImportJobStatus[] = ["queued", "fetching", "processing"];

interface PendingImportsPanelProps {
  // Already fetched by AccountPage via listMySubmissions() — this component only filters it, it
  // doesn't fetch recipes itself.
  submissions: Recipe[];
  // Already fetched by AccountPage too — used only to resolve a pending recipe's category_id to
  // a display name for the "AI-selected category" label below, since the category the worker
  // picked (see worker/app/handlers.py's _resolve_category_id) is otherwise just an opaque id.
  categories: Category[];
  onAcknowledged: (recipe: Recipe) => void;
  // Called on every background poll while a job is still active (see the effect below) — a job
  // settling to "done" means a brand new recipe now exists, and this component has no other way
  // to learn about it (it only ever receives `submissions` as a prop). Without this, a just-
  // finished import wouldn't show up here until the next full page load.
  onImportsPolled?: () => void;
  // Bumped by AccountPage every time its sibling ImportManager creates or approves a job — this
  // component fetches its own, independent copy of the jobs list, so without an explicit nudge it
  // would only ever notice a *new* job on its own next poll tick, and it only polls at all once
  // its own state already contains something active. A job created after this panel last saw zero
  // active jobs would otherwise never be picked up, not even after a delay.
  reloadTrigger?: number;
}

export function PendingImportsPanel({
  submissions,
  categories,
  onAcknowledged,
  onImportsPolled,
  reloadTrigger,
}: PendingImportsPanelProps) {
  const { t } = useLanguage();
  const { user } = useAuth();
  const [jobs, setJobs] = useState<ImportJob[]>([]);
  const [error, setError] = useState<string | null>(null);

  const categoryName = (categoryId: number): string | null =>
    categories.find((category) => category.id === categoryId)?.name ?? null;

  // GET /imports returns every user's jobs for an admin caller (needed for backoffice
  // moderation) — this is a personal review panel on the Account page, not a moderation tool, so
  // it's narrowed to the viewer's own regardless of role. Cross-user triage lives on the
  // dedicated Failed Imports back office page instead.
  const myJobs = jobs.filter((job) => job.created_by_username === user?.username);

  const reload = () => api.listImportJobs().then(setJobs).catch((e) => setError(String(e)));

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!reloadTrigger) return;
    reload();
    // Also refresh submissions right away, not just once the subsequent 3s poll tick fires — a
    // trivially fast import (or one that was already done by the time this fires) shouldn't have
    // to wait out a full poll interval before its recipe shows up.
    onImportsPolled?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reloadTrigger]);

  // Same polling pattern as ImportManager/RecipeManager — a job failing while this page is open
  // should surface here without a manual refresh, and a job finishing should surface its recipe
  // the same way (via onImportsPolled, since the recipe itself lives in the parent's state).
  useEffect(() => {
    if (!myJobs.some((job) => ACTIVE.includes(job.status))) return;
    const interval = setInterval(() => {
      reload();
      onImportsPolled?.();
    }, 3000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobs]);

  const pendingRecipes = submissions.filter((recipe) => recipe.source_url && !recipe.import_reviewed_at);
  const failedJobs = myJobs.filter((job) => job.status === "failed" && !job.dismissed_at);

  const handleAcknowledge = async (recipe: Recipe) => {
    setError(null);
    try {
      const updated = await api.acknowledgeImportedRecipe(recipe.id);
      onAcknowledged(updated);
    } catch (e) {
      setError(String(e));
    }
  };

  const handleDismiss = async (job: ImportJob) => {
    setError(null);
    try {
      await api.dismissFailedImport(job.id);
      setJobs((current) => current.filter((j) => j.id !== job.id));
    } catch (e) {
      setError(String(e));
    }
  };

  if (pendingRecipes.length === 0 && failedJobs.length === 0) return null;

  return (
    <div className="mt-4 space-y-4">
      {error && (
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {pendingRecipes.length > 0 && (
        <div className="rounded-md bg-olive-light p-4">
          <h3 className="font-serif text-lg font-semibold text-ink">
            {t.account.pendingImportsHeading}
          </h3>
          <ul className="mt-3 flex flex-wrap items-stretch gap-4">
            {pendingRecipes.map((recipe) => (
              <li key={recipe.id} className="flex w-48 flex-col rounded-md bg-cream-card p-3 shadow-sm">
                {recipe.images[0] ? (
                  <img
                    src={`${BASE_URL}${recipe.images[0]}`}
                    alt={recipe.title}
                    className="h-28 w-full rounded-md object-cover"
                  />
                ) : (
                  <div className="flex h-28 w-full items-center justify-center rounded-md bg-olive-light text-xs text-ink/50">
                    {recipe.title}
                  </div>
                )}
                <p className="mt-2 line-clamp-2 text-sm font-medium text-ink">{recipe.title}</p>
                {categoryName(recipe.category_id) && (
                  <p className="mt-0.5 text-xs text-ink/50">
                    {t.account.aiCategoryLabel.replace(
                      "{category}",
                      categoryName(recipe.category_id) ?? ""
                    )}
                  </p>
                )}
                {isInstagramImport(recipe) && (
                  <p className="mt-1 text-xs text-terracotta">
                    {t.account.instagramPlayButtonWarning}
                  </p>
                )}
                {/* Pinned to the card's bottom edge, same reasoning as the "My recipes" grid
                    (frontend/src/account/AccountPage.tsx) — a longer title or category label
                    would otherwise push this card's controls lower than its neighbors'. */}
                <div className="mt-auto flex flex-wrap items-center gap-3 pt-2">
                  <Link
                    to={`/recipes/${recipe.id}/edit`}
                    className="text-xs text-terracotta hover:underline"
                  >
                    {t.account.editRecipeLink}
                  </Link>
                  <button
                    type="button"
                    onClick={() => handleAcknowledge(recipe)}
                    className={secondaryButton}
                  >
                    {t.account.pendingImportsOk}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {failedJobs.length > 0 && (
        <div className="rounded-md bg-red-50 p-4">
          <h3 className="font-serif text-lg font-semibold text-ink">
            {t.account.failedImportsHeading}
          </h3>
          <ul className="mt-3 divide-y divide-red-100">
            {failedJobs.map((job) => (
              <li key={job.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
                <div>
                  <p className="break-all text-sm text-ink">{job.source}</p>
                  <p className="mt-1 text-sm text-red-700">
                    {job.error_kind === "disallowed"
                      ? t.account.errorDisallowed
                      : t.account.errorTechnical}
                  </p>
                </div>
                <div className="flex shrink-0 flex-wrap items-center gap-3">
                  <Link to="/submit-recipe" className="text-xs text-terracotta hover:underline">
                    {t.account.addManuallyInstead}
                  </Link>
                  <button type="button" onClick={() => handleDismiss(job)} className={secondaryButton}>
                    {t.account.dismissImport}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

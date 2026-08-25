import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
// Shared with the back office — the API already scopes /imports to "my own jobs" for a non-admin
// caller (and "everyone's" for an admin), so the same component works unmodified in both places.
import { BookmarkImportPanel } from "../backoffice/BookmarkImportPanel";
import { ImportManager } from "../backoffice/ImportManager";
import { useLanguage } from "../i18n/LanguageContext";
import { primaryButton } from "../ui/buttonStyles";
import { useConfirm } from "../ui/useConfirm";
import { PendingImportsPanel } from "./PendingImportsPanel";
import { RecipeList } from "./RecipeList";
import { matchesSearchWords } from "../ui/searchMatch";
import { useRecipeSearch } from "../ui/useRecipeSearch";
import type { Category, Recipe } from "../types";

// Reachable via the "Add or import recipes" button on the recipes page (and the header nav) —
// everything a logged-in user needs to get a new recipe into the app, whether by hand or via
// URL/bookmark import, plus the list of what they've already added. Split out of AccountPage,
// which now covers only the profile/password section — see README Design Decisions, "Splitting
// Import out of the account page".
export function ImportPage() {
  const { t } = useLanguage();
  const [submissions, setSubmissions] = useState<Recipe[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [error, setError] = useState<string | null>(null);
  // Bumped whenever ImportManager creates/approves a job — see PendingImportsPanel's
  // reloadTrigger prop for why this hand-off is needed.
  const [importTrigger, setImportTrigger] = useState(0);
  const { confirm, confirmDialog } = useConfirm();
  const { text: searchText, setText: setSearchText, search } = useRecipeSearch();

  const reloadSubmissions = () =>
    api.listMySubmissions().then(setSubmissions).catch((e) => setError(String(e)));

  // The full list is already loaded unpaginated (see api.listMySubmissions) — filtering
  // client-side avoids a backend change for a list that never had pagination to begin with.
  const filteredSubmissions = search
    ? submissions.filter((recipe) => matchesSearchWords(recipe.title, search))
    : submissions;

  useEffect(() => {
    reloadSubmissions();
    api.listCategories().then(setCategories).catch((e) => setError(String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleToggleShare = async (recipe: Recipe) => {
    setError(null);
    try {
      const updated = await api.toggleShare(recipe.id, !recipe.is_shared);
      setSubmissions((current) => current.map((r) => (r.id === updated.id ? updated : r)));
    } catch (e) {
      setError(String(e));
    }
  };

  const handleAcknowledgeImport = (updated: Recipe) => {
    setSubmissions((current) => current.map((r) => (r.id === updated.id ? updated : r)));
  };

  const handleChangeCategory = async (recipe: Recipe, categoryId: number) => {
    setError(null);
    try {
      const updated = await api.updateRecipeCategory(recipe.id, categoryId);
      setSubmissions((current) => current.map((r) => (r.id === updated.id ? updated : r)));
    } catch (e) {
      setError(String(e));
    }
  };

  const handleDelete = async (recipe: Recipe) => {
    if (!(await confirm(t.recipeManager.confirmDelete))) return;
    setError(null);
    try {
      await api.deleteRecipe(recipe.id);
      setSubmissions((current) => current.filter((r) => r.id !== recipe.id));
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <div className="space-y-6">
      <section className="rounded-lg bg-cream-card p-5 ring-1 ring-black/5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-serif text-2xl font-semibold text-ink">
            {t.browser.addOrImportButton}
          </h2>
          <Link to="/submit-recipe" className={primaryButton}>
            {t.account.addRecipeLink}
          </Link>
        </div>
        {error && (
          <p role="alert" className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}
        <PendingImportsPanel
          submissions={submissions}
          categories={categories}
          onAcknowledged={handleAcknowledgeImport}
          onImportsPolled={reloadSubmissions}
          reloadTrigger={importTrigger}
        />
        <ImportManager
          onJobCreated={() => setImportTrigger((t) => t + 1)}
          reloadTrigger={importTrigger}
        />
        <BookmarkImportPanel onJobCreated={() => setImportTrigger((t) => t + 1)} />

        <h3 className="mt-6 font-serif text-xl font-semibold text-ink">
          {t.account.myRecipesHeading}
        </h3>
        {submissions.length === 0 ? (
          <p className="mt-2 text-sm text-ink/60">{t.account.noRecipes}</p>
        ) : (
          <>
            <input
              type="search"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              placeholder={t.account.searchPlaceholder}
              aria-label={t.account.searchPlaceholder}
              className="mt-2 w-full max-w-sm rounded-md border border-olive/30 bg-white px-3 py-2 text-sm text-ink focus:border-terracotta focus:outline-none"
            />
            {filteredSubmissions.length === 0 ? (
              <p className="mt-2 text-sm text-ink/60">{t.account.noSearchResults}</p>
            ) : (
              <RecipeList
                recipes={filteredSubmissions}
                showStatus
                showEditLink
                onToggleShare={handleToggleShare}
                onDelete={handleDelete}
                categories={categories}
                onChangeCategory={handleChangeCategory}
              />
            )}
          </>
        )}
      </section>
      {confirmDialog}
    </div>
  );
}

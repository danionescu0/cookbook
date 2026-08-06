import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, BASE_URL } from "../api/client";
// Shared with the back office — the API already scopes /imports to "my own jobs" for a non-admin
// caller (and "everyone's" for an admin), so the same component works unmodified in both places.
import { ImportManager } from "../backoffice/ImportManager";
import { useLanguage } from "../i18n/LanguageContext";
import { primaryButton } from "../ui/buttonStyles";
import { PendingImportsPanel } from "./PendingImportsPanel";
import type { Category, Recipe, UserProfile } from "../types";

const inputClasses =
  "rounded-md border border-olive/30 bg-white px-3 py-2 text-sm text-ink focus:border-terracotta focus:outline-none";

interface RecipeListProps {
  recipes: Recipe[];
  showStatus?: boolean;
  // Only meaningful for a list of recipes the viewer actually owns (e.g. not favorites, which can
  // include other users' shared recipes) — gates the Edit link to /recipes/{id}/edit.
  showEditLink?: boolean;
  onToggleShare?: (recipe: Recipe) => void;
  categories?: Category[];
  onChangeCategory?: (recipe: Recipe, categoryId: number) => void;
}

function RecipeList({
  recipes,
  showStatus,
  showEditLink,
  onToggleShare,
  categories,
  onChangeCategory,
}: RecipeListProps) {
  const { t } = useLanguage();
  return (
    <ul className="mt-3 flex flex-wrap gap-4">
      {recipes.map((recipe) => (
        <li key={recipe.id} className="w-40">
          <Link to={`/recipes/${recipe.id}`} className="block">
            {recipe.images[0] ? (
              <img
                src={`${BASE_URL}${recipe.images[0]}`}
                alt={recipe.title}
                className="h-28 w-40 rounded-md object-cover"
              />
            ) : (
              <div className="flex h-28 w-40 items-center justify-center rounded-md bg-olive-light text-xs text-ink/50">
                {recipe.title}
              </div>
            )}
            <p className="mt-1 text-sm text-ink">
              {recipe.title}
              {showStatus && <em className="ml-1 text-xs text-ink/50 not-italic">({recipe.status})</em>}
            </p>
            {recipe.source_url && (
              <p className="text-xs text-ink/50">{t.account.importedBadge}</p>
            )}
          </Link>
          {showEditLink && (
            <Link
              to={`/recipes/${recipe.id}/edit`}
              className="mt-1 block text-xs text-terracotta hover:underline"
            >
              {t.account.editRecipeLink}
            </Link>
          )}
          {/* Imports (source_url set) never get a sharing control — always private. */}
          {onToggleShare && !recipe.source_url && (
            <button
              type="button"
              onClick={() => onToggleShare(recipe)}
              className="mt-1 text-xs text-terracotta hover:underline"
            >
              {recipe.is_shared ? t.account.unshareAction : t.account.shareAction}
            </button>
          )}
          {onChangeCategory && categories && (
            <select
              aria-label={t.recipeManager.categoryLabel}
              value={recipe.category_id}
              onChange={(e) => onChangeCategory(recipe, Number(e.target.value))}
              className="mt-1 w-full rounded-md border border-olive/30 bg-white px-1.5 py-1 text-xs text-ink focus:border-terracotta focus:outline-none"
            >
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </select>
          )}
        </li>
      ))}
    </ul>
  );
}

export function AccountPage() {
  const { t } = useLanguage();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [favorites, setFavorites] = useState<Recipe[]>([]);
  const [submissions, setSubmissions] = useState<Recipe[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [error, setError] = useState<string | null>(null);
  // Bumped whenever ImportManager creates/approves a job — see PendingImportsPanel's
  // reloadTrigger prop for why this hand-off is needed.
  const [importTrigger, setImportTrigger] = useState(0);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSaved, setPasswordSaved] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);

  const reloadSubmissions = () =>
    api.listMySubmissions().then(setSubmissions).catch((e) => setError(String(e)));

  useEffect(() => {
    api.me().then(setProfile).catch((e) => setError(String(e)));
    api.listFavorites().then(setFavorites).catch((e) => setError(String(e)));
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

  const handleChangePassword = async (event: React.FormEvent) => {
    event.preventDefault();
    setPasswordError(null);
    setPasswordSaved(false);
    setChangingPassword(true);
    try {
      await api.changePassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setPasswordSaved(true);
    } catch (e) {
      setPasswordError(String(e));
    } finally {
      setChangingPassword(false);
    }
  };

  return (
    <div className="space-y-6">
      <section className="rounded-lg bg-cream-card p-5 ring-1 ring-black/5">
        <h2 className="font-serif text-2xl font-semibold text-ink">{t.account.heading}</h2>
        {error && (
          <p role="alert" className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}
        {profile && (
          <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
            <dt className="text-ink/60">{t.account.usernameLabel}</dt>
            <dd className="text-ink">{profile.username}</dd>
            <dt className="text-ink/60">{t.account.emailLabel}</dt>
            <dd className="text-ink">{profile.email ?? t.account.emailNotSet}</dd>
          </dl>
        )}

        <h3 className="mt-5 font-serif text-lg font-semibold text-ink">
          {t.account.changePasswordHeading}
        </h3>
        <form onSubmit={handleChangePassword} className="mt-2 flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label htmlFor="account-current-password" className="text-sm font-medium text-ink/70">
              {t.account.currentPasswordLabel}
            </label>
            <input
              id="account-current-password"
              type="password"
              autoComplete="current-password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className={inputClasses}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="account-new-password" className="text-sm font-medium text-ink/70">
              {t.account.newPasswordLabel}
            </label>
            <input
              id="account-new-password"
              type="password"
              autoComplete="new-password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className={inputClasses}
            />
          </div>
          <button type="submit" disabled={changingPassword} className={primaryButton}>
            {t.account.changePasswordSubmit}
          </button>
        </form>
        {passwordError && (
          <p role="alert" className="mt-2 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {passwordError}
          </p>
        )}
        {passwordSaved && !passwordError && (
          <p role="status" className="mt-2 rounded-md bg-olive-light px-3 py-2 text-sm text-ink">
            {t.account.changePasswordSuccess}
          </p>
        )}
      </section>

      <section className="rounded-lg bg-cream-card p-5 ring-1 ring-black/5">
        <h3 className="font-serif text-xl font-semibold text-ink">{t.account.favoritesHeading}</h3>
        {favorites.length === 0 ? (
          <p className="mt-2 text-sm text-ink/60">{t.account.noFavorites}</p>
        ) : (
          <RecipeList recipes={favorites} />
        )}
      </section>

      <section className="rounded-lg bg-cream-card p-5 ring-1 ring-black/5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-serif text-xl font-semibold text-ink">
            {t.account.myRecipesHeading}
          </h3>
          <Link to="/submit-recipe" className={primaryButton}>
            {t.account.addRecipeLink}
          </Link>
        </div>
        <PendingImportsPanel
          submissions={submissions}
          onAcknowledged={handleAcknowledgeImport}
          onImportsPolled={reloadSubmissions}
          reloadTrigger={importTrigger}
        />
        <ImportManager onJobCreated={() => setImportTrigger((t) => t + 1)} />
        {submissions.length === 0 ? (
          <p className="mt-2 text-sm text-ink/60">{t.account.noRecipes}</p>
        ) : (
          <RecipeList
            recipes={submissions}
            showStatus
            showEditLink
            onToggleShare={handleToggleShare}
            categories={categories}
            onChangeCategory={handleChangeCategory}
          />
        )}
      </section>
    </div>
  );
}

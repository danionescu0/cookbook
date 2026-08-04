import { Fragment, useEffect, useState } from "react";
import { api } from "../api/client";
import { useLanguage } from "../i18n/LanguageContext";
import { hostnameOf } from "../ui/hostnameOf";
import { Pagination } from "../ui/Pagination";
import { secondaryButton } from "../ui/buttonStyles";
import type { Recipe, UserAdmin } from "../types";

const RECIPES_PAGE_SIZE = 10;

function formatDate(iso: string | null): string | null {
  if (!iso) return null;
  return new Date(iso).toLocaleDateString();
}

interface UserRecipesRowProps {
  username: string;
  colSpan: number;
}

// The expanded "Show recipes" panel for one user — its own fetch/pagination state, independent
// of the outer users table, so switching between users' panels doesn't fight over a single
// shared page number.
function UserRecipesRow({ username, colSpan }: UserRecipesRowProps) {
  const { t } = useLanguage();
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listRecipesPage({ owner: username, limit: RECIPES_PAGE_SIZE, offset: (page - 1) * RECIPES_PAGE_SIZE })
      .then(({ items, total: newTotal }) => {
        setRecipes(items);
        setTotal(newTotal);
      })
      .catch((e) => setError(String(e)));
  }, [username, page]);

  const totalPages = Math.max(1, Math.ceil(total / RECIPES_PAGE_SIZE));

  return (
    <tr>
      <td colSpan={colSpan} className="bg-olive-light/40 px-4 py-4">
        {error && (
          <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}
        {!error && recipes.length === 0 && (
          <p className="text-sm text-ink/60">{t.usersManager.noRecipes}</p>
        )}
        {recipes.length > 0 && (
          <ul className="divide-y divide-olive-light/70">
            {recipes.map((recipe) => (
              <li key={recipe.id} className="flex flex-wrap items-center gap-2 py-2 text-sm">
                <span className="text-ink">{recipe.title}</span>
                <em className="text-ink/50 not-italic">({recipe.status})</em>
                {recipe.is_shared && (
                  <span className="rounded-full bg-olive/10 px-2 py-0.5 text-xs font-medium text-olive">
                    {t.recipeManager.sharedBadge}
                  </span>
                )}
                {recipe.source_url && (
                  <a
                    href={recipe.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-terracotta hover:underline"
                  >
                    {t.recipeManager.importedFrom.replace("{domain}", hostnameOf(recipe.source_url))}
                  </a>
                )}
              </li>
            ))}
          </ul>
        )}
        <Pagination
          currentPage={page}
          totalPages={totalPages}
          onPageChange={setPage}
          ariaLabel={t.usersManager.recipesPaginationLabel}
          previousLabel={t.usersManager.previousPage}
          nextLabel={t.usersManager.nextPage}
        />
      </td>
    </tr>
  );
}

export function UsersManager() {
  const { t } = useLanguage();
  const [users, setUsers] = useState<UserAdmin[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [expandedUsername, setExpandedUsername] = useState<string | null>(null);

  useEffect(() => {
    api
      .listUsers()
      .then(setUsers)
      .catch((e) => setError(String(e)));
  }, []);

  const columnCount = 9;

  return (
    <div>
      <h3 className="font-serif text-lg font-semibold text-ink">{t.usersManager.heading}</h3>

      {error && (
        <p role="alert" className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-max border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-olive-light text-ink/60">
              <th className="py-2 pr-4 font-medium">{t.usersManager.username}</th>
              <th className="py-2 pr-4 font-medium">{t.usersManager.email}</th>
              <th className="py-2 pr-4 font-medium">{t.usersManager.status}</th>
              <th className="py-2 pr-4 font-medium">{t.usersManager.createdAt}</th>
              <th className="py-2 pr-4 font-medium">{t.usersManager.lastLogin}</th>
              <th className="py-2 pr-4 text-right font-medium">{t.usersManager.imported}</th>
              <th className="py-2 pr-4 text-right font-medium">{t.usersManager.owned}</th>
              <th className="py-2 pr-4 text-right font-medium">{t.usersManager.shared}</th>
              <th className="py-2 font-medium">{t.usersManager.actions}</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <Fragment key={user.id}>
                <tr className="border-b border-olive-light/60">
                  <td className="py-2 pr-4 text-ink">{user.username}</td>
                  <td className="py-2 pr-4 text-ink/80">{user.email ?? "—"}</td>
                  <td className="py-2 pr-4">
                    <span
                      className={
                        "rounded-full px-2 py-0.5 text-xs font-medium " +
                        (user.is_verified
                          ? "bg-olive/10 text-olive"
                          : "bg-terracotta/10 text-terracotta")
                      }
                    >
                      {user.is_verified ? t.usersManager.confirmed : t.usersManager.unconfirmed}
                    </span>
                  </td>
                  <td className="py-2 pr-4 text-ink/80">{formatDate(user.created_at)}</td>
                  <td className="py-2 pr-4 text-ink/80">
                    {formatDate(user.last_login_at) ?? t.usersManager.never}
                  </td>
                  <td className="py-2 pr-4 text-right text-ink/80">{user.imported_recipes_count}</td>
                  <td className="py-2 pr-4 text-right text-ink/80">{user.owned_recipes_count}</td>
                  <td className="py-2 pr-4 text-right text-ink/80">{user.shared_recipes_count}</td>
                  <td className="py-2">
                    <button
                      type="button"
                      onClick={() =>
                        setExpandedUsername(expandedUsername === user.username ? null : user.username)
                      }
                      className={secondaryButton}
                    >
                      {expandedUsername === user.username
                        ? t.usersManager.hideRecipes
                        : t.usersManager.showRecipes}
                    </button>
                  </td>
                </tr>
                {expandedUsername === user.username && (
                  <UserRecipesRow username={user.username} colSpan={columnCount} />
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

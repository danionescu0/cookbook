import { Link } from "react-router-dom";
import { BASE_URL } from "../api/client";
import { useLanguage } from "../i18n/LanguageContext";
import type { Category, Recipe } from "../types";

interface RecipeListProps {
  recipes: Recipe[];
  showStatus?: boolean;
  // Only meaningful for a list of recipes the viewer actually owns (e.g. not favorites, which can
  // include other users' shared recipes) — gates the Edit link to /recipes/{id}/edit.
  showEditLink?: boolean;
  onToggleShare?: (recipe: Recipe) => void;
  onDelete?: (recipe: Recipe) => void;
  onSend?: (recipe: Recipe) => void;
  categories?: Category[];
  onChangeCategory?: (recipe: Recipe, categoryId: number) => void;
}

export function RecipeList({
  recipes,
  showStatus,
  showEditLink,
  onToggleShare,
  onDelete,
  onSend,
  categories,
  onChangeCategory,
}: RecipeListProps) {
  const { t } = useLanguage();
  return (
    <ul className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
      {recipes.map((recipe) => (
        <li key={recipe.id} className="flex flex-col">
          <Link to={`/recipes/${recipe.id}`} className="block">
            {recipe.images[0] ? (
              <img
                src={`${BASE_URL}${recipe.images[0]}`}
                alt={recipe.title}
                className="aspect-4/3 w-full rounded-md object-cover"
              />
            ) : (
              <div className="aspect-4/3 flex w-full items-center justify-center rounded-md bg-olive-light text-xs text-ink/50">
                {recipe.title}
              </div>
            )}
            <p className="mt-1 line-clamp-2 text-sm text-ink">
              {recipe.title}
              {showStatus && <em className="ml-1 text-xs text-ink/50 not-italic">({recipe.status})</em>}
            </p>
            {recipe.source_url && (
              <p className="text-xs text-ink/50">{t.account.importedBadge}</p>
            )}
          </Link>
          {/* Pinned to the card's bottom edge (not just after the text above) so a short title
              and a title that wraps to two lines still land the edit link/share button/category
              select at the same height across a row — otherwise a longer title pushes its own
              card's controls further down than its neighbors', a non-uniform "jagged" grid. */}
          <div className="mt-auto pt-1">
            {showEditLink && (
              <Link
                to={`/recipes/${recipe.id}/edit`}
                className="block text-xs text-terracotta hover:underline"
              >
                {t.account.editRecipeLink}
              </Link>
            )}
            {onDelete && (
              <button
                type="button"
                onClick={() => onDelete(recipe)}
                className="block text-xs text-red-600 hover:underline"
              >
                {t.recipeManager.delete}
              </button>
            )}
            {onSend && (
              <button
                type="button"
                onClick={() => onSend(recipe)}
                className="block text-xs text-terracotta hover:underline"
              >
                {t.sharing.sendAction}
              </button>
            )}
            {/* Imports (source_url set) never get a sharing control — always private. */}
            {onToggleShare && !recipe.source_url && (
              <button
                type="button"
                onClick={() => onToggleShare(recipe)}
                className="text-xs text-terracotta hover:underline"
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
          </div>
        </li>
      ))}
    </ul>
  );
}

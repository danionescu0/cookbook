import { useLanguage } from "../i18n/LanguageContext";
import type { Category } from "../types";

interface CategoryNavProps {
  categories: Category[];
  selectedCategoryId: number | null;
  onSelect: (categoryId: number | null) => void;
  // Only a logged-in viewer has favorites to filter by — omit entirely rather than rendering a
  // pill that would just 401.
  showFavorites?: boolean;
  favoritesActive?: boolean;
  onToggleFavorites?: () => void;
}

export function CategoryNav({
  categories,
  selectedCategoryId,
  onSelect,
  showFavorites,
  favoritesActive,
  onToggleFavorites,
}: CategoryNavProps) {
  const { t } = useLanguage();

  return (
    <nav aria-label="Categories" className="flex flex-wrap gap-2">
      <button type="button" onClick={() => onSelect(null)} className={pillClasses(selectedCategoryId === null)}>
        {t.browser.all}
      </button>
      {categories.map((category) => (
        <button
          key={category.id}
          type="button"
          onClick={() => onSelect(category.id)}
          className={pillClasses(selectedCategoryId === category.id)}
        >
          {category.name}
        </button>
      ))}
      {/* A separate, independent toggle (not part of the single-select group above) — combines
          with whichever category is selected rather than replacing it, so "Favorites" +
          "Desserts" narrows to favorited desserts. Given its own color family (not terracotta,
          the category-active color) so it reads as a different kind of filter at a glance. */}
      {showFavorites && (
        <button
          type="button"
          onClick={onToggleFavorites}
          aria-pressed={favoritesActive}
          className={favoritesPillClasses(Boolean(favoritesActive))}
        >
          ♥ {t.browser.favoritesFilter}
        </button>
      )}
    </nav>
  );
}

function pillClasses(active: boolean): string {
  return [
    "shrink-0 rounded-full px-4 py-2 text-sm font-medium transition-colors",
    active ? "bg-terracotta text-white" : "bg-olive-light text-ink hover:bg-olive/20",
  ].join(" ");
}

function favoritesPillClasses(active: boolean): string {
  return [
    "shrink-0 rounded-full px-4 py-2 text-sm font-medium transition-colors",
    active ? "bg-rose-600 text-white" : "bg-rose-50 text-rose-700 hover:bg-rose-100",
  ].join(" ");
}

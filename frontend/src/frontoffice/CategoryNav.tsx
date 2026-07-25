import { useLanguage } from "../i18n/LanguageContext";
import type { Category } from "../types";

interface CategoryNavProps {
  categories: Category[];
  selectedCategoryId: number | null;
  onSelect: (categoryId: number | null) => void;
}

export function CategoryNav({ categories, selectedCategoryId, onSelect }: CategoryNavProps) {
  const { t } = useLanguage();

  return (
    <nav
      aria-label="Categories"
      className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-2 sm:mx-0 sm:px-0"
    >
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
    </nav>
  );
}

function pillClasses(active: boolean): string {
  return [
    "shrink-0 rounded-full px-4 py-2 text-sm font-medium transition-colors",
    active ? "bg-terracotta text-white" : "bg-olive-light text-ink hover:bg-olive/20",
  ].join(" ");
}

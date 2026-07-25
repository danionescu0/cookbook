import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useLanguage } from "../i18n/LanguageContext";
import { CategoryNav } from "./CategoryNav";
import { RecipeCard } from "./RecipeCard";
import type { Category, Recipe } from "../types";

export function RecipeBrowser() {
  const { language, t } = useLanguage();
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null);
  const [recipes, setRecipes] = useState<Recipe[]>([]);

  useEffect(() => {
    api.listCategories().then(setCategories);
  }, []);

  useEffect(() => {
    api.listRecipes(selectedCategoryId ?? undefined, language).then((all) =>
      setRecipes(all.filter((recipe) => recipe.status === "approved"))
    );
  }, [selectedCategoryId, language]);

  return (
    <section aria-labelledby="browse-heading" className="space-y-6">
      <div>
        <h2 id="browse-heading" className="font-serif text-3xl font-semibold text-ink">
          {t.browser.heading}
        </h2>
        <p className="mt-1 text-ink/60">{t.browser.subtitle}</p>
      </div>

      <CategoryNav
        categories={categories}
        selectedCategoryId={selectedCategoryId}
        onSelect={setSelectedCategoryId}
      />

      {recipes.length === 0 ? (
        <p className="text-ink/60">{t.browser.empty}</p>
      ) : (
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {recipes.map((recipe) => (
            <RecipeCard key={recipe.id} recipe={recipe} />
          ))}
        </div>
      )}
    </section>
  );
}

import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useFavoriteIds } from "../auth/useFavoriteIds";
import { useLanguage } from "../i18n/LanguageContext";
import { CategoryNav } from "./CategoryNav";
import { RecipeCard } from "./RecipeCard";
import type { Category, Recipe } from "../types";

interface RecipeGridProps {
  recipes: Recipe[];
  favoriteIds: Set<number>;
  onToggleFavorite?: (recipeId: number) => void;
}

function RecipeGrid({ recipes, favoriteIds, onToggleFavorite }: RecipeGridProps) {
  return (
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
      {recipes.map((recipe) => (
        <RecipeCard
          key={recipe.id}
          recipe={recipe}
          isFavorited={favoriteIds.has(recipe.id)}
          onToggleFavorite={onToggleFavorite}
        />
      ))}
    </div>
  );
}

export function RecipeBrowser() {
  const { language, t } = useLanguage();
  const { user, isAuthenticated } = useAuth();
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null);
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const { favoriteIds, toggleFavorite } = useFavoriteIds();

  useEffect(() => {
    api.listCategories().then(setCategories);
  }, []);

  useEffect(() => {
    api.listRecipes(selectedCategoryId ?? undefined, language).then(setRecipes);
  }, [selectedCategoryId, language]);

  // The API already scopes the list to what this viewer may see (their own recipes, any status,
  // plus everyone else's shared+approved ones) — this just splits that single response into the
  // two sections, it doesn't do any additional filtering itself.
  const mine = isAuthenticated ? recipes.filter((r) => r.owner_username === user!.username) : [];
  const community = isAuthenticated
    ? recipes.filter((r) => r.owner_username !== user!.username)
    : recipes;
  const primary = isAuthenticated ? mine : community;

  return (
    <div className="space-y-10">
      <section aria-labelledby="browse-heading" className="space-y-6">
        <div>
          <h2 id="browse-heading" className="font-serif text-3xl font-semibold text-ink">
            {isAuthenticated ? t.browser.myRecipesHeading : t.browser.heading}
          </h2>
          <p className="mt-1 text-ink/60">{t.browser.subtitle}</p>
        </div>

        <CategoryNav
          categories={categories}
          selectedCategoryId={selectedCategoryId}
          onSelect={setSelectedCategoryId}
        />

        {primary.length === 0 ? (
          <p className="text-ink/60">{t.browser.empty}</p>
        ) : (
          <RecipeGrid
            recipes={primary}
            favoriteIds={favoriteIds}
            onToggleFavorite={isAuthenticated ? toggleFavorite : undefined}
          />
        )}
      </section>

      {isAuthenticated && community.length > 0 && (
        <section aria-labelledby="community-heading" className="space-y-4">
          <h3 id="community-heading" className="font-serif text-xl font-semibold text-ink">
            {t.browser.communityHeading}
          </h3>
          <RecipeGrid recipes={community} favoriteIds={favoriteIds} onToggleFavorite={toggleFavorite} />
        </section>
      )}
    </div>
  );
}

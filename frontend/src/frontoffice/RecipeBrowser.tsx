import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useFavoriteIds } from "../auth/useFavoriteIds";
import { useLanguage } from "../i18n/LanguageContext";
import { useSeoMeta } from "../seo/useSeoMeta";
import { CategoryNav } from "./CategoryNav";
import { RecipeCard } from "./RecipeCard";
import { useInfiniteRecipes } from "./useInfiniteRecipes";
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
  const { favoriteIds, toggleFavorite } = useFavoriteIds();

  useSeoMeta({ title: `${t.brand} — ${t.browser.heading}` });

  useEffect(() => {
    api.listCategories().then(setCategories);
  }, []);

  // Two independent infinite-scroll feeds rather than one list split client-side: "mine" is
  // unbounded in principle, so a single feed ordered across both would make community content
  // arbitrarily hard to reach. Each keeps loading on its own as its own sentinel scrolls into
  // view — see useInfiniteRecipes.
  const mine = useInfiniteRecipes({
    categoryId: selectedCategoryId ?? undefined,
    language,
    owner: "me",
    enabled: isAuthenticated,
  });
  const publicFeed = useInfiniteRecipes({
    categoryId: selectedCategoryId ?? undefined,
    language,
    onlyPublic: true,
  });
  // A viewer's own shared+approved recipe is returned by both feeds (owner="me" doesn't care
  // about sharing status, only_public doesn't care about ownership) — drop it from this one so
  // it isn't shown twice.
  const community = isAuthenticated
    ? publicFeed.recipes.filter((r) => r.owner_username !== user!.username)
    : publicFeed.recipes;

  const primary = isAuthenticated ? mine : publicFeed;
  const primaryRecipes = isAuthenticated ? mine.recipes : community;
  const showCommunitySection = isAuthenticated && (community.length > 0 || publicFeed.loading);

  return (
    <div className="space-y-10">
      <section aria-labelledby="browse-heading" className="space-y-6">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <div>
            <h2 id="browse-heading" className="font-serif text-3xl font-semibold text-ink">
              {isAuthenticated ? t.browser.myRecipesHeading : t.browser.heading}
            </h2>
            <p className="mt-1 text-ink/60">{t.browser.subtitle}</p>
          </div>
          {showCommunitySection && (
            <a href="#community-heading" className="text-sm text-terracotta hover:underline">
              {t.browser.jumpToCommunity}
            </a>
          )}
        </div>

        <CategoryNav
          categories={categories}
          selectedCategoryId={selectedCategoryId}
          onSelect={setSelectedCategoryId}
        />

        {primary.error && (
          <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {primary.error}
          </p>
        )}

        {primaryRecipes.length === 0 && !primary.loading ? (
          <p className="text-ink/60">{t.browser.empty}</p>
        ) : (
          <>
            <RecipeGrid
              recipes={primaryRecipes}
              favoriteIds={favoriteIds}
              onToggleFavorite={isAuthenticated ? toggleFavorite : undefined}
            />
            {primary.loading && <p className="text-sm text-ink/50">{t.browser.loadingMore}</p>}
            {primary.hasMore && <div ref={primary.sentinelRef} aria-hidden="true" className="h-1" />}
          </>
        )}
      </section>

      {showCommunitySection && (
        <section id="community-heading" aria-labelledby="community-heading-title" className="space-y-4">
          <h3 id="community-heading-title" className="font-serif text-xl font-semibold text-ink">
            {t.browser.communityHeading}
          </h3>
          {publicFeed.error && (
            <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
              {publicFeed.error}
            </p>
          )}
          <RecipeGrid recipes={community} favoriteIds={favoriteIds} onToggleFavorite={toggleFavorite} />
          {publicFeed.loading && <p className="text-sm text-ink/50">{t.browser.loadingMore}</p>}
          {publicFeed.hasMore && (
            <div ref={publicFeed.sentinelRef} aria-hidden="true" className="h-1" />
          )}
        </section>
      )}
    </div>
  );
}

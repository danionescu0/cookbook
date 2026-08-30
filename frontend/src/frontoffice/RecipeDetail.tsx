import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useFavoriteIds } from "../auth/useFavoriteIds";
import { useLanguage } from "../i18n/LanguageContext";
import { ShareRecipeDialog } from "../sharing/ShareRecipeDialog";
import { RecipeDetailView } from "./RecipeDetailView";
import type { Nutrition, Recipe } from "../types";

// The original, unprefixed route (/recipes/:id) — kept working for internal navigation
// (backoffice/account links) rather than removed. Public/shareable links use the
// language-prefixed, slug-based PublicRecipeDetail instead; this page points its canonical tag
// there when the recipe is actually public, so search engines don't treat the two as duplicates.
export function RecipeDetail() {
  const { id } = useParams<{ id: string }>();
  const { language, t } = useLanguage();
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [nutrition, setNutrition] = useState<Nutrition | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const { isAuthenticated, favoriteIds, toggleFavorite } = useFavoriteIds();

  useEffect(() => {
    if (!id) return;
    setRecipe(null);
    setNutrition(null);
    setError(null);
    api
      .getRecipe(Number(id), language)
      .then(setRecipe)
      .catch((e) => setError(String(e)));
    // Nutrition is best-effort: a recipe that hasn't been enriched yet (or a lookup hiccup)
    // shouldn't block the rest of the page from rendering, so failures here are swallowed.
    api
      .getNutrition(Number(id))
      .then(setNutrition)
      .catch(() => setNutrition(null));
  }, [id, language]);

  if (error) {
    return (
      <div>
        <p role="alert">{error}</p>
        <Link to={`/${language}`} className="text-terracotta hover:underline">
          {t.detail.back}
        </Link>
      </div>
    );
  }

  if (!recipe) {
    return <p className="text-ink/60">{t.detail.loading}</p>;
  }

  if (recipe.status !== "approved") {
    return (
      <div>
        <p>{t.detail.notPublished}</p>
        <Link to={`/${language}`} className="text-terracotta hover:underline">
          {t.detail.back}
        </Link>
      </div>
    );
  }

  const canonical = recipe.is_shared
    ? `${window.location.origin}/${language}/recipes/${recipe.id}-${recipe.slug}`
    : undefined;

  return (
    <>
      <RecipeDetailView
        recipe={recipe}
        nutrition={nutrition}
        isAuthenticated={isAuthenticated}
        isFavorited={favoriteIds.has(recipe.id)}
        onToggleFavorite={() => toggleFavorite(recipe.id)}
        backTo={`/${language}`}
        seo={{ canonical }}
        onSend={() => setSending(true)}
      />
      {sending && <ShareRecipeDialog recipe={recipe} onClose={() => setSending(false)} />}
    </>
  );
}

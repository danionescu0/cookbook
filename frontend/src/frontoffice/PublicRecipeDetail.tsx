import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useFavoriteIds } from "../auth/useFavoriteIds";
import { isLanguage } from "../i18n/config";
import { useLanguage } from "../i18n/LanguageContext";
import { RecipeDetailView } from "./RecipeDetailView";
import type { Nutrition, Recipe } from "../types";

// "42" or "42-lemon-tart" — the id is what's actually resolved server-side (see
// api/app/routers/recipes.py); the slug suffix is decorative and only checked here to redirect
// to the canonical form. This also makes a language switch trivial: navigate to /{lang}/recipes/
// {id} (always valid, no slug lookup needed) and let the canonicalizing effect below take it
// from there once the new language's slug loads.
const ID_SLUG_RE = /^(\d+)(?:-(.*))?$/;

export function PublicRecipeDetail() {
  const { lang, idSlug } = useParams<{ lang: string; idSlug: string }>();
  const navigate = useNavigate();
  const { t } = useLanguage();
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [nutrition, setNutrition] = useState<Nutrition | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { isAuthenticated, favoriteIds, toggleFavorite } = useFavoriteIds();

  const match = idSlug?.match(ID_SLUG_RE);
  const recipeId = match ? Number(match[1]) : NaN;
  const providedSlug = match?.[2];
  const validRoute = Boolean(lang && isLanguage(lang)) && !Number.isNaN(recipeId);

  useEffect(() => {
    if (!validRoute) return;
    setRecipe(null);
    setNutrition(null);
    setError(null);
    api
      .getRecipe(recipeId, lang)
      .then(setRecipe)
      .catch((e) => setError(String(e)));
    api
      .getNutrition(recipeId)
      .then(setNutrition)
      .catch(() => setNutrition(null));
  }, [validRoute, recipeId, lang]);

  useEffect(() => {
    // Canonicalize: a bare id, a stale slug (title edited since, or a language switch that
    // landed here before the new language's slug was known), or any other mismatch all redirect
    // to the current, correct /{lang}/recipes/{id}-{slug} URL.
    if (recipe && recipe.slug !== providedSlug) {
      navigate(`/${lang}/recipes/${recipe.id}-${recipe.slug}`, { replace: true });
    }
  }, [recipe, providedSlug, lang, navigate]);

  if (!validRoute) {
    return <Navigate to="/" replace />;
  }

  if (error) {
    return (
      <div>
        <p role="alert">{error}</p>
        <Link to={`/${lang}`} className="text-terracotta hover:underline">
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
        <Link to={`/${lang}`} className="text-terracotta hover:underline">
          {t.detail.back}
        </Link>
      </div>
    );
  }

  return (
    <RecipeDetailView
      recipe={recipe}
      nutrition={nutrition}
      isAuthenticated={isAuthenticated}
      isFavorited={favoriteIds.has(recipe.id)}
      onToggleFavorite={() => toggleFavorite(recipe.id)}
      backTo={`/${lang}`}
      seo={{ canonical: `${window.location.origin}/${lang}/recipes/${recipe.id}-${recipe.slug}` }}
    />
  );
}

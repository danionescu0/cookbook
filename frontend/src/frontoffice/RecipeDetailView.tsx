import { Link } from "react-router-dom";
import { BASE_URL } from "../api/client";
import { useLanguage } from "../i18n/LanguageContext";
import { isSectionHeader, stripSectionHeader } from "./recipeSections";
import { useSeoMeta } from "../seo/useSeoMeta";
import { ImageSlider } from "./ImageSlider";
import { NutritionPanel } from "./NutritionPanel";
import { hostnameOf } from "../ui/hostnameOf";
import type { Nutrition, Recipe } from "../types";

export interface RecipeDetailSeo {
  // Absolute URL of the canonical (language-prefixed, slug) page for this recipe — omitted when
  // the recipe isn't public (nothing to canonicalize to). Per-language hreflang alternates are
  // deliberately left to sitemap.xml rather than duplicated here (see api/app/routers/sitemap.py)
  // — search engines only need one consistent hreflang source, and the sitemap already has every
  // translation's slug at hand without an extra request.
  canonical?: string;
}

interface RecipeDetailViewProps {
  recipe: Recipe;
  nutrition: Nutrition | null;
  isAuthenticated: boolean;
  isFavorited: boolean;
  onToggleFavorite: () => void;
  backTo: string;
  seo: RecipeDetailSeo;
}

export function RecipeDetailView({
  recipe,
  nutrition,
  isAuthenticated,
  isFavorited,
  onToggleFavorite,
  backTo,
  seo,
}: RecipeDetailViewProps) {
  const { t } = useLanguage();
  const imageUrl = recipe.images[0] ? `${BASE_URL}${recipe.images[0]}` : undefined;
  const allImageUrls = recipe.images.map((image) => `${BASE_URL}${image}`);
  // Only a manually-added, approved, owner-opted-in-to-share recipe is actually public — see
  // routers/recipes.py's visibility rule. Everything else (private, or shared but still pending
  // moderation) must never get indexing signals or structured data, even though its owner can
  // still view this same page.
  const isPublic = recipe.status === "approved" && recipe.is_shared;

  useSeoMeta({
    title: `${recipe.title} — ${t.brand}`,
    description: recipe.description || undefined,
    image: imageUrl,
    canonical: isPublic ? seo.canonical : undefined,
    noindex: !isPublic,
  });

  const gramsByIndex = new Map(
    (nutrition?.per_ingredient ?? []).map((item) => [item.index, item.estimated_grams])
  );

  return (
    <article className="mx-auto max-w-3xl">
      {isPublic && (
        <script type="application/ld+json">
          {JSON.stringify({
            "@context": "https://schema.org",
            "@type": "Recipe",
            name: recipe.title,
            ...(allImageUrls.length > 0 ? { image: allImageUrls } : {}),
            ...(recipe.description ? { description: recipe.description } : {}),
            recipeIngredient: recipe.ingredients.map(stripSectionHeader),
            recipeInstructions: recipe.steps.map(stripSectionHeader),
            inLanguage: recipe.language,
            ...(recipe.approved_at ? { datePublished: recipe.approved_at } : {}),
            ...(nutrition?.estimated_servings
              ? { recipeYield: `${nutrition.estimated_servings}` }
              : {}),
            // Deliberately per-serving, matching recipeYield above — schema.org's
            // NutritionInformation is documented as being scoped to one serving of the recipe,
            // not the whole dish's totals (see README Design Decisions, "Recipe structured data").
            ...(nutrition?.per_serving
              ? {
                  nutrition: {
                    "@type": "NutritionInformation",
                    calories: `${Math.round(nutrition.per_serving.calories)} calories`,
                    proteinContent: `${Math.round(nutrition.per_serving.protein_g)} g`,
                    carbohydrateContent: `${Math.round(nutrition.per_serving.carbs_g)} g`,
                    sugarContent: `${Math.round(nutrition.per_serving.sugars_g)} g`,
                    fatContent: `${Math.round(nutrition.per_serving.fat_g)} g`,
                  },
                }
              : {}),
          })}
        </script>
      )}

      <Link to={backTo} className="text-sm text-terracotta hover:underline">
        {t.detail.back}
      </Link>

      <div className="mt-2 flex flex-wrap items-center gap-3">
        <h1 className="font-serif text-3xl font-semibold text-ink sm:text-4xl">{recipe.title}</h1>
        {isAuthenticated && (
          <button
            type="button"
            onClick={onToggleFavorite}
            aria-pressed={isFavorited}
            className={
              "flex h-9 w-9 items-center justify-center rounded-full text-xl ring-1 ring-black/5 transition-colors " +
              (isFavorited
                ? "bg-terracotta text-white"
                : "bg-cream-card text-ink/60 hover:text-terracotta")
            }
          >
            <span aria-hidden="true">{isFavorited ? "♥" : "♡"}</span>
            <span className="sr-only">
              {isFavorited ? t.detail.removeFavorite : t.detail.addFavorite}
            </span>
          </button>
        )}
      </div>

      <ImageSlider images={recipe.images} alt={recipe.title} />

      {recipe.description && <p className="mt-4 text-lg text-ink/80">{recipe.description}</p>}

      <div className="mt-8 grid gap-8 sm:grid-cols-[1fr_2fr]">
        {recipe.ingredients.length > 0 && (
          <section aria-labelledby="ingredients-heading">
            <h2 id="ingredients-heading" className="font-serif text-xl font-semibold text-ink">
              {t.detail.ingredients}
            </h2>
            <ul className="mt-3 space-y-2">
              {recipe.ingredients.map((ingredient, index) => {
                if (isSectionHeader(ingredient)) {
                  return (
                    <li
                      key={index}
                      className="mt-4 font-serif font-semibold text-ink first:mt-0"
                    >
                      {stripSectionHeader(ingredient)}
                    </li>
                  );
                }
                const grams = gramsByIndex.get(index);
                return (
                  <li key={index} className="flex gap-2 text-ink/90">
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-terracotta" />
                    <span>
                      {ingredient}
                      {grams !== undefined && (
                        <span className="text-ink/50"> ({Math.round(grams)}g)</span>
                      )}
                    </span>
                  </li>
                );
              })}
            </ul>
          </section>
        )}

        {recipe.steps.length > 0 && (
          <section aria-labelledby="steps-heading">
            <h2 id="steps-heading" className="font-serif text-xl font-semibold text-ink">
              {t.detail.steps}
            </h2>
            <ol className="mt-3 space-y-4">
              {(() => {
                let stepNumber = 0;
                return recipe.steps.map((step, index) => {
                  if (isSectionHeader(step)) {
                    return (
                      <li key={index} className="mt-2 font-serif font-semibold text-ink first:mt-0">
                        {stripSectionHeader(step)}
                      </li>
                    );
                  }
                  stepNumber += 1;
                  return (
                    <li key={index} className="flex gap-3">
                      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-terracotta text-sm font-semibold text-white">
                        {stepNumber}
                      </span>
                      <span className="text-ink/90">{step}</span>
                    </li>
                  );
                });
              })()}
            </ol>
          </section>
        )}
      </div>

      {recipe.tips.length > 0 && (
        <section aria-labelledby="tips-heading" className="mt-8 rounded-lg bg-olive-light p-4">
          <h2 id="tips-heading" className="font-serif text-xl font-semibold text-ink">
            {t.detail.tips}
          </h2>
          <ul className="mt-3 space-y-2">
            {recipe.tips.map((tip) => (
              <li key={tip} className="text-ink/90">
                {tip}
              </li>
            ))}
          </ul>
        </section>
      )}

      {nutrition && <NutritionPanel nutrition={nutrition} />}

      {recipe.source_url && (
        <p className="mt-8 border-t border-black/10 pt-4 text-sm">
          <a
            href={recipe.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-terracotta hover:underline"
          >
            {t.detail.sourceLink.replace("{domain}", hostnameOf(recipe.source_url))}
          </a>
        </p>
      )}
    </article>
  );
}

import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, BASE_URL } from "../api/client";
import { useLanguage } from "../i18n/LanguageContext";
import type { Recipe } from "../types";

export function RecipeDetail() {
  const { id } = useParams<{ id: string }>();
  const { language, t } = useLanguage();
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setRecipe(null);
    setError(null);
    api
      .getRecipe(Number(id), language)
      .then(setRecipe)
      .catch((e) => setError(String(e)));
  }, [id, language]);

  if (error) {
    return (
      <div>
        <p role="alert">{error}</p>
        <Link to="/" className="text-terracotta hover:underline">
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
        <Link to="/" className="text-terracotta hover:underline">
          {t.detail.back}
        </Link>
      </div>
    );
  }

  const image = recipe.images[0];

  return (
    <article className="mx-auto max-w-3xl">
      <Link to="/" className="text-sm text-terracotta hover:underline">
        {t.detail.back}
      </Link>

      <h1 className="mt-2 font-serif text-3xl font-semibold text-ink sm:text-4xl">
        {recipe.title}
      </h1>

      {image && (
        <div className="mt-4 aspect-video w-full overflow-hidden rounded-lg bg-olive-light">
          <img
            src={`${BASE_URL}${image}`}
            alt={recipe.title}
            className="h-full w-full object-cover"
          />
        </div>
      )}

      {recipe.description && <p className="mt-4 text-lg text-ink/80">{recipe.description}</p>}

      <div className="mt-8 grid gap-8 sm:grid-cols-[1fr_2fr]">
        {recipe.ingredients.length > 0 && (
          <section aria-labelledby="ingredients-heading">
            <h2 id="ingredients-heading" className="font-serif text-xl font-semibold text-ink">
              {t.detail.ingredients}
            </h2>
            <ul className="mt-3 space-y-2">
              {recipe.ingredients.map((ingredient) => (
                <li key={ingredient} className="flex gap-2 text-ink/90">
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-terracotta" />
                  {ingredient}
                </li>
              ))}
            </ul>
          </section>
        )}

        {recipe.steps.length > 0 && (
          <section aria-labelledby="steps-heading">
            <h2 id="steps-heading" className="font-serif text-xl font-semibold text-ink">
              {t.detail.steps}
            </h2>
            <ol className="mt-3 space-y-4">
              {recipe.steps.map((step, index) => (
                <li key={step} className="flex gap-3">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-terracotta text-sm font-semibold text-white">
                    {index + 1}
                  </span>
                  <span className="text-ink/90">{step}</span>
                </li>
              ))}
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
    </article>
  );
}

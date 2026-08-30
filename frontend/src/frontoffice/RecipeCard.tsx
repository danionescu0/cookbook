import { Link } from "react-router-dom";
import { BASE_URL } from "../api/client";
import { useLanguage } from "../i18n/LanguageContext";
import type { Recipe } from "../types";

interface RecipeCardProps {
  recipe: Recipe;
  isFavorited?: boolean;
  onToggleFavorite?: (recipeId: number) => void;
  onSend?: (recipe: Recipe) => void;
}

export function RecipeCard({ recipe, isFavorited, onToggleFavorite, onSend }: RecipeCardProps) {
  const { t, language } = useLanguage();
  const image = recipe.images[0];

  return (
    <Link
      to={`/${language}/recipes/${recipe.id}-${recipe.slug}`}
      className="group relative block overflow-hidden rounded-lg bg-cream-card shadow-sm ring-1 ring-black/5 transition-shadow hover:shadow-md"
    >
      <div className="absolute right-2 top-2 z-10 flex flex-col gap-2">
        {onToggleFavorite && (
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              onToggleFavorite(recipe.id);
            }}
            aria-label={isFavorited ? t.browser.removeFavorite : t.browser.addFavorite}
            aria-pressed={isFavorited}
            className={
              "flex h-8 w-8 items-center justify-center rounded-full text-lg shadow-sm transition-colors " +
              (isFavorited ? "bg-terracotta text-white" : "bg-white/90 text-ink/60 hover:text-terracotta")
            }
          >
            {isFavorited ? "♥" : "♡"}
          </button>
        )}
        {onSend && (
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              onSend(recipe);
            }}
            aria-label={t.sharing.sendAction}
            className="flex h-8 w-8 items-center justify-center rounded-full bg-white/90 text-ink/60 shadow-sm transition-colors hover:text-terracotta"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-4 w-4"
              aria-hidden="true"
            >
              <circle cx="18" cy="5" r="3" />
              <circle cx="6" cy="12" r="3" />
              <circle cx="18" cy="19" r="3" />
              <line x1="8.59" y1="10.51" x2="15.42" y2="6.49" />
              <line x1="8.59" y1="13.49" x2="15.42" y2="17.51" />
            </svg>
          </button>
        )}
      </div>
      <div className="aspect-4/3 w-full overflow-hidden bg-olive-light">
        {image ? (
          <img
            src={`${BASE_URL}${image}`}
            alt={recipe.title}
            loading="lazy"
            className="h-full w-full object-cover transition-transform group-hover:scale-105"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-sm text-ink/40">
            {t.browser.noImage}
          </div>
        )}
      </div>
      <div className="p-4">
        <h3 className="font-serif text-lg font-semibold text-ink">{recipe.title}</h3>
        {recipe.description && (
          <p className="mt-1 line-clamp-2 text-sm text-ink/70">{recipe.description}</p>
        )}
      </div>
    </Link>
  );
}

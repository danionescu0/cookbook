import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useLanguage } from "../i18n/LanguageContext";
import { useSeoMeta } from "../seo/useSeoMeta";
import { primaryButton, secondaryButton } from "../ui/buttonStyles";
import { RecipeCard } from "./RecipeCard";
import type { Recipe } from "../types";

const COMMUNITY_PREVIEW_COUNT = 8;

export function LandingPage() {
  const { t, language, supportedLanguages } = useLanguage();
  const [communityRecipes, setCommunityRecipes] = useState<Recipe[]>([]);

  useSeoMeta({
    title: `${t.brand} — ${t.landing.heading}`,
    description: t.landing.tagline,
    // Points at the language-prefixed canonical entry point even when rendered at bare "/" —
    // avoids the two URLs reading as duplicate content to a crawler.
    canonical: `${window.location.origin}/${language}`,
    hreflangAlternates: Object.fromEntries(
      supportedLanguages.map((lang) => [lang, `${window.location.origin}/${lang}`])
    ),
  });

  useEffect(() => {
    // Unauthenticated, so the API already scopes this to the shared+approved pool — nothing
    // private ever reaches this page.
    api
      .listRecipes(undefined, language)
      .then((recipes) => setCommunityRecipes(recipes.slice(0, COMMUNITY_PREVIEW_COUNT)))
      .catch(() => setCommunityRecipes([]));
  }, [language]);

  return (
    <div className="space-y-16 pb-8">
      <section className="grid items-center gap-10 pt-4 lg:grid-cols-2 lg:gap-16">
        <div>
          <h1 className="font-serif text-4xl font-semibold leading-tight text-ink sm:text-5xl">
            {t.landing.heading}
          </h1>
          <p className="mt-4 max-w-md text-base text-ink/70">{t.landing.tagline}</p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link to={`/${language}/recipes`} className={primaryButton}>
              {t.landing.ctaBrowse}
            </Link>
            <Link to="/signup" className={secondaryButton}>
              {t.landing.ctaSignup}
            </Link>
          </div>
        </div>

        {/* Signature element: the site's own pitch, laid out like a recipe card's ingredient
            list — ties the marketing copy to the subject instead of a generic feature list. */}
        <div className="rounded-lg bg-cream-card p-6 ring-1 ring-black/5 sm:p-8">
          <p className="font-serif text-xl font-semibold text-ink">{t.landing.cardTitle}</p>
          <ul className="mt-4 space-y-3">
            {t.landing.ingredients.map((line) => (
              <li key={line} className="flex gap-3 text-sm text-ink/80">
                <span aria-hidden="true" className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-terracotta" />
                {line}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section>
        <h2 className="font-serif text-2xl font-semibold text-ink">{t.landing.howItWorksHeading}</h2>
        <ol className="mt-6 grid gap-6 sm:grid-cols-3">
          {t.landing.steps.map((step, index) => (
            <li key={step.title}>
              <span className="font-serif text-3xl font-semibold text-terracotta/60">
                {String(index + 1).padStart(2, "0")}
              </span>
              <h3 className="mt-1 font-serif text-lg font-semibold text-ink">{step.title}</h3>
              <p className="mt-1 text-sm text-ink/70">{step.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section>
        <h2 className="font-serif text-2xl font-semibold text-ink">{t.landing.featuresHeading}</h2>
        <div className="mt-6 grid gap-4 sm:grid-cols-3">
          {t.landing.features.map((feature) => (
            <div key={feature.title} className="rounded-lg bg-cream-card p-5 ring-1 ring-black/5">
              <h3 className="font-serif text-lg font-semibold text-ink">{feature.title}</h3>
              <p className="mt-1 text-sm text-ink/70">{feature.body}</p>
            </div>
          ))}
        </div>
      </section>

      {communityRecipes.length > 0 && (
        <section>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="font-serif text-2xl font-semibold text-ink">
              {t.landing.communityHeading}
            </h2>
            <Link to={`/${language}/recipes`} className="text-sm text-terracotta hover:underline">
              {t.landing.ctaBrowse}
            </Link>
          </div>
          <div className="mt-6 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {communityRecipes.map((recipe) => (
              <RecipeCard key={recipe.id} recipe={recipe} />
            ))}
          </div>
        </section>
      )}

      <section className="rounded-lg bg-olive-light p-8 text-center">
        <h2 className="font-serif text-2xl font-semibold text-ink">{t.landing.finalCtaHeading}</h2>
        <p className="mx-auto mt-2 max-w-md text-sm text-ink/70">{t.landing.finalCtaBody}</p>
        <div className="mt-5 flex flex-wrap justify-center gap-3">
          <Link to="/signup" className={primaryButton}>
            {t.landing.ctaSignup}
          </Link>
          <Link to={`/${language}/recipes`} className={secondaryButton}>
            {t.landing.ctaBrowse}
          </Link>
        </div>
      </section>

      {/* Last element on the page, so it's discoverable without competing with the signup/browse
          CTAs above — but sized to match the feature headings (e.g. "Translated, not guessed")
          rather than fading into fine print. */}
      <div className="mx-auto max-w-md space-y-4 text-center">
        <p className="font-serif text-lg font-semibold text-ink">{t.landing.supportText}</p>
        <a
          href="https://www.buymeacoffee.com/danionescu"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 rounded-md bg-[#FFDD00] px-5 py-2.5 text-sm font-semibold text-black shadow-sm transition-transform hover:scale-105"
        >
          {t.landing.supportCta}
        </a>
      </div>
    </div>
  );
}

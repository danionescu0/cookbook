import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { api, BASE_URL } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { GoogleSignInButton } from "../auth/GoogleSignInButton";
import { useLanguage } from "../i18n/LanguageContext";
import { RecipeDetailView } from "../frontoffice/RecipeDetailView";
import { useSeoMeta } from "../seo/useSeoMeta";
import { primaryButton } from "../ui/buttonStyles";
import { setPendingShareToken } from "./pendingShare";
import type { Nutrition, RecipeShareDetail } from "../types";

function hoursUntil(iso: string): number {
  return Math.max(0, Math.round((new Date(iso).getTime() - Date.now()) / (60 * 60 * 1000)));
}

export function SharePage() {
  const { token } = useParams<{ token: string }>();
  const { t, language } = useLanguage();
  const { isAuthenticated, user } = useAuth();
  const navigate = useNavigate();

  const [detail, setDetail] = useState<RecipeShareDetail | null>(null);
  const [nutrition, setNutrition] = useState<Nutrition | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [googleClientId, setGoogleClientId] = useState("");
  const [googleError, setGoogleError] = useState<string | null>(null);
  const [copying, setCopying] = useState(false);
  const [copyError, setCopyError] = useState<string | null>(null);

  // Re-fetched whenever auth state changes: the same GET returns just a teaser while logged out
  // and the full recipe once authenticated — see api/app/routers/recipe_shares.py's get_share.
  useEffect(() => {
    if (!token) return;
    setDetail(null);
    setError(null);
    api
      .getRecipeShare(token)
      .then(setDetail)
      .catch((e) => setError(String(e)));
  }, [token, isAuthenticated]);

  useEffect(() => {
    const recipeId = detail?.recipe?.id;
    if (recipeId === undefined) return;
    api
      .getNutrition(recipeId)
      .then(setNutrition)
      .catch(() => setNutrition(null));
  }, [detail?.recipe?.id]);

  // Set as soon as an unauthenticated visitor lands here — this is what lets App.tsx's
  // pending-share redirect bring them back to this exact page once they finish signing up
  // (manual signup needs an email-verify hop through two other pages first) or logging in.
  useEffect(() => {
    if (!isAuthenticated && token) setPendingShareToken(token);
  }, [isAuthenticated, token]);

  useEffect(() => {
    api
      .getPublicSettings()
      .then((settings) => setGoogleClientId(settings.google_client_id))
      .catch(() => setGoogleClientId(""));
  }, []);

  // RecipeDetailView (rendered below once authenticated + active) calls useSeoMeta itself with
  // the recipe's own title/description/image — this call only needs to cover the states where
  // that component isn't rendered at all (loading/error/expired/teaser). Computing the same
  // title RecipeDetailView would in the "has a recipe" case keeps the two idempotent regardless
  // of which of the two (parent vs. child) effect happens to run last in a given commit.
  useSeoMeta({
    title: detail?.recipe
      ? `${detail.recipe.title} — ${t.brand}`
      : `${t.sharing.teaserTitle} — ${t.brand}`,
    noindex: true, // a private, expiring, per-recipient link must never be indexed
  });

  const handleCopy = async () => {
    if (!token) return;
    setCopying(true);
    setCopyError(null);
    try {
      const copied = await api.copyRecipeShare(token);
      navigate(`/recipes/${copied.id}/edit`);
    } catch (e) {
      setCopyError(String(e));
      setCopying(false);
    }
  };

  if (!token) {
    return <Navigate to="/" replace />;
  }

  if (error) {
    return (
      <p role="alert" className="mx-auto max-w-sm rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
        {error}
      </p>
    );
  }

  if (!detail) {
    return <p className="text-ink/60">{t.detail.loading}</p>;
  }

  if (detail.status !== "active") {
    return (
      <section className="mx-auto max-w-sm rounded-lg bg-cream-card p-6 text-center ring-1 ring-black/5">
        <p className="text-ink/70">
          {detail.status === "expired" ? t.sharing.linkExpired : t.sharing.linkRevoked}
        </p>
        <Link to="/" className="mt-4 inline-block text-sm text-terracotta hover:underline">
          {t.detail.back}
        </Link>
      </section>
    );
  }

  const hoursLeft = hoursUntil(detail.expires_at);
  const expiresLine = t.sharing.expiresInHours.replace("{hours}", String(hoursLeft));
  // The sender opening their own link (e.g. testing it, or re-clicking it from their own chat) —
  // copying it into the same account they already own it under makes no sense, so this is the one
  // case the "Copy to my recipes" CTA is withheld rather than shown unconditionally to anyone
  // authenticated.
  const isOwnRecipe = detail.recipe?.owner_user_id === user?.id;

  // Not yet authenticated: the teaser tile + sign-up/sign-in CTAs. The full recipe (below) only
  // ever comes from the server once authenticated — this branch never has it to show even if it
  // wanted to.
  if (!detail.recipe) {
    const imageUrl = detail.teaser?.image ? `${BASE_URL}${detail.teaser.image}` : undefined;
    return (
      <section className="mx-auto max-w-sm rounded-lg bg-cream-card p-6 ring-1 ring-black/5">
        {imageUrl ? (
          <img
            src={imageUrl}
            alt={detail.teaser?.title ?? ""}
            className="h-40 w-full rounded-md object-cover"
          />
        ) : (
          <div className="flex h-40 w-full items-center justify-center rounded-md bg-olive-light text-sm text-ink/50">
            {detail.teaser?.title}
          </div>
        )}
        <h2 className="mt-4 font-serif text-2xl font-semibold text-ink">{detail.teaser?.title}</h2>
        {detail.teaser?.description && (
          <p className="mt-2 text-sm text-ink/70">{detail.teaser.description}</p>
        )}
        <p className="mt-3 text-xs text-ink/50">{expiresLine}</p>

        <p className="mt-5 text-sm font-medium text-ink">{t.sharing.signInPrompt}</p>
        {googleClientId && (
          <div className="mt-3 flex justify-center">
            <GoogleSignInButton clientId={googleClientId} language={language} onError={setGoogleError} />
          </div>
        )}
        {googleError && (
          <p role="alert" className="mt-2 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {googleError}
          </p>
        )}
        <div className="mt-3 flex flex-col gap-1 text-sm">
          <Link to="/signup" className="text-terracotta hover:underline">
            {t.sharing.createAccountLink}
          </Link>
          <span className="text-xs text-ink/50">{t.sharing.createAccountHint}</span>
          <Link to="/login" className="mt-2 text-terracotta hover:underline">
            {t.sharing.logInLink}
          </Link>
        </div>
      </section>
    );
  }

  // Authenticated with an active share: show the full recipe (read the same way any other detail
  // page does, via the shared RecipeDetailView) plus a persistent "copy" CTA. isAuthenticated is
  // deliberately passed as false here to hide RecipeDetailView's favorite button — favoriting
  // goes through the normal visibility rule (see routers/recipes.py), which this recipe doesn't
  // pass for a non-owner viewer even with a valid share token, so wiring it up would just 404.
  return (
    <div className="space-y-4">
      <section className="rounded-lg bg-cream-card p-4 ring-1 ring-black/5">
        <p className="text-sm text-ink/70">
          {detail.shared_by_email
            ? t.sharing.sharedByLabel.replace("{email}", detail.shared_by_email)
            : null}{" "}
          <span className="text-ink/50">{expiresLine}</span>
        </p>
        {isOwnRecipe ? (
          <p className="mt-3 text-sm text-ink/60">{t.sharing.ownRecipeNotice}</p>
        ) : (
          <button type="button" onClick={handleCopy} disabled={copying} className={`${primaryButton} mt-3`}>
            {copying ? t.sharing.copyingButton : t.sharing.copyToMyRecipes}
          </button>
        )}
        {copyError && (
          <p role="alert" className="mt-2 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {copyError}
          </p>
        )}
      </section>

      <RecipeDetailView
        recipe={detail.recipe}
        nutrition={nutrition}
        isAuthenticated={false}
        isFavorited={false}
        onToggleFavorite={() => {}}
        backTo="/"
        seo={{}}
      />
    </div>
  );
}

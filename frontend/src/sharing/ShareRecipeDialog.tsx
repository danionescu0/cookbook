import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../api/client";
import { useLanguage } from "../i18n/LanguageContext";
import { primaryButton, secondaryButton } from "../ui/buttonStyles";
import type { Recipe, RecipeShare } from "../types";

interface ShareRecipeDialogProps {
  recipe: Recipe;
  onClose: () => void;
}

// Mirrors the server's own routers/recipe_shares.py::_share_status — computed client-side from
// the same two timestamps so the list below doesn't need a round-trip just to show "expired".
function shareStatus(share: RecipeShare): "active" | "expired" | "revoked" {
  if (share.revoked_at) return "revoked";
  return new Date(share.expires_at).getTime() < Date.now() ? "expired" : "active";
}

// Sender-side "Send to a friend" panel. Branches on whether the recipe is already public (shared
// with the community *and* approved — the same condition routers/recipes.py's `_is_public` checks
// server-side): a public recipe already has a permanent, no-account-needed URL
// (`/{lang}/recipes/{id}-{slug}`, the same one PublicRecipeDetail/the sitemap use), so this just
// shows/copies that — no `recipe_shares` row, no expiry, nothing to generate. A private recipe
// gets the real `recipe_shares` flow: generate/list/revoke 24h links behind a sign-up wall. Same
// portal/backdrop/animation shell as ui/ConfirmDialog.tsx, but with its own body (a list, not a
// single yes/no choice) — see README Design Decisions ("Recipe sharing").
export function ShareRecipeDialog({ recipe, onClose }: ShareRecipeDialogProps) {
  const { t, language } = useLanguage();
  const isPublic = recipe.status === "approved" && recipe.is_shared;
  const publicUrl = `${window.location.origin}/${language}/recipes/${recipe.id}-${recipe.slug}`;

  const [shares, setShares] = useState<RecipeShare[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [copiedToken, setCopiedToken] = useState<string | null>(null);

  const reload = () =>
    api
      .listRecipeShares(recipe.id)
      .then(setShares)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));

  useEffect(() => {
    // The public branch never lists/generates recipe_shares rows — nothing to fetch.
    if (!isPublic) reload();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleGenerate = async () => {
    setCreating(true);
    setError(null);
    try {
      const share = await api.createRecipeShare(recipe.id);
      setShares((current) => [share, ...current]);
    } catch (e) {
      setError(String(e));
    } finally {
      setCreating(false);
    }
  };

  // `key` is the share's token for a private link, or the literal "public" for the permanent
  // public URL — either way, just what `copiedToken` compares against to show "Copied!" on the
  // right row/button and nowhere else.
  const handleCopyLink = (url: string, key: string) => {
    navigator.clipboard.writeText(url).then(() => {
      setCopiedToken(key);
      setTimeout(() => setCopiedToken((current) => (current === key ? null : current)), 2000);
    });
  };

  const handleRevoke = async (share: RecipeShare) => {
    setError(null);
    try {
      await api.revokeRecipeShare(recipe.id, share.id);
      setShares((current) =>
        current.map((s) => (s.id === share.id ? { ...s, revoked_at: new Date().toISOString() } : s))
      );
    } catch (e) {
      setError(String(e));
    }
  };

  return createPortal(
    <div
      role="presentation"
      onClick={onClose}
      className="motion-safe-dialog-animation fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4 backdrop-blur-sm"
      style={{ animation: "dialog-backdrop-in 150ms ease-out" }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="share-dialog-heading"
        onClick={(event) => event.stopPropagation()}
        className="motion-safe-dialog-animation w-full max-w-md rounded-lg bg-cream-card p-6 shadow-xl ring-1 ring-black/5"
        style={{ animation: "dialog-panel-in 180ms ease-out" }}
      >
        <div className="flex items-start justify-between gap-2">
          <h2 id="share-dialog-heading" className="font-serif text-xl font-semibold text-ink">
            {t.sharing.dialogHeading}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={t.common.cancel}
            className="text-ink/50 hover:text-ink"
          >
            ✕
          </button>
        </div>
        <p className="mt-1 text-sm text-ink/70">{recipe.title}</p>

        {error && (
          <p role="alert" className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}

        {isPublic ? (
          <>
            <p className="mt-4 text-sm text-ink/70">{t.sharing.publicLinkNotice}</p>
            <div className="mt-3 flex items-center gap-2">
              <input
                type="text"
                readOnly
                value={publicUrl}
                onFocus={(e) => e.currentTarget.select()}
                className="min-w-0 flex-1 rounded-md border border-olive/30 bg-white px-3 py-2 text-sm text-ink"
              />
              <button
                type="button"
                onClick={() => handleCopyLink(publicUrl, "public")}
                className={secondaryButton}
              >
                {copiedToken === "public" ? t.sharing.copiedConfirmation : t.sharing.copyLinkButton}
              </button>
            </div>
          </>
        ) : (
          <>
            <button
              type="button"
              onClick={handleGenerate}
              disabled={creating}
              className={`${primaryButton} mt-4`}
            >
              {creating ? t.sharing.generatingButton : t.sharing.generateButton}
            </button>
            <p className="mt-1 text-xs text-ink/50">{t.sharing.linkExpiryNotice}</p>
          </>
        )}

        {!isPublic && (
          <div className="mt-4 max-h-64 space-y-2 overflow-y-auto">
            {loading ? (
              <p className="text-sm text-ink/60">{t.detail.loading}</p>
            ) : shares.length === 0 ? (
              <p className="text-sm text-ink/60">{t.sharing.noSharesYet}</p>
            ) : (
              shares.map((share) => {
                const status = shareStatus(share);
                return (
                  <div key={share.id} className="rounded-md border border-olive/30 bg-white p-3 text-sm">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-ink/70">
                        {status === "active" &&
                          t.sharing.expiresLabel.replace(
                            "{time}",
                            new Date(share.expires_at).toLocaleString()
                          )}
                        {status === "expired" && t.sharing.linkExpired}
                        {status === "revoked" && t.sharing.linkRevoked}
                      </span>
                      {status === "active" && (
                        <div className="flex shrink-0 gap-2">
                          <button
                            type="button"
                            onClick={() =>
                              handleCopyLink(`${window.location.origin}/share/${share.token}`, share.token)
                            }
                            className="text-xs text-terracotta hover:underline"
                          >
                            {copiedToken === share.token
                              ? t.sharing.copiedConfirmation
                              : t.sharing.copyLinkButton}
                          </button>
                          <button
                            type="button"
                            onClick={() => handleRevoke(share)}
                            className="text-xs text-red-600 hover:underline"
                          >
                            {t.sharing.revokeAction}
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        )}

        <button type="button" onClick={onClose} className={`${secondaryButton} mt-4`}>
          {t.common.close}
        </button>
      </div>
    </div>,
    document.body
  );
}

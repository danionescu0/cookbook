import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "./AuthContext";

// Shared between RecipeBrowser and RecipeDetail — both need to know which recipes the current
// user has favorited and how to toggle one, with an optimistic update that reverts on failure.
export function useFavoriteIds() {
  const { isAuthenticated } = useAuth();
  const [favoriteIds, setFavoriteIds] = useState<Set<number>>(new Set());

  useEffect(() => {
    if (!isAuthenticated) {
      setFavoriteIds(new Set());
      return;
    }
    api.listFavorites().then((recipes) => setFavoriteIds(new Set(recipes.map((r) => r.id))));
  }, [isAuthenticated]);

  const toggleFavorite = useCallback(
    async (recipeId: number) => {
      const wasFavorited = favoriteIds.has(recipeId);
      setFavoriteIds((current) => {
        const next = new Set(current);
        if (wasFavorited) next.delete(recipeId);
        else next.add(recipeId);
        return next;
      });
      try {
        if (wasFavorited) await api.unfavoriteRecipe(recipeId);
        else await api.favoriteRecipe(recipeId);
      } catch {
        setFavoriteIds((current) => {
          const next = new Set(current);
          if (wasFavorited) next.add(recipeId);
          else next.delete(recipeId);
          return next;
        });
      }
    },
    [favoriteIds]
  );

  return { isAuthenticated, favoriteIds, toggleFavorite };
}

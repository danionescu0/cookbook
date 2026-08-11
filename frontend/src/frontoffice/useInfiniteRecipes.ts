import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { Recipe } from "../types";

const PAGE_SIZE = 12;

interface UseInfiniteRecipesParams {
  categoryId?: number;
  language: string;
  owner?: "me";
  onlyPublic?: boolean;
  // Combinable with categoryId — see api/client.ts's listRecipesPage.
  favoritesOnly?: boolean;
  // False skips fetching entirely (e.g. the "mine" list when nobody's logged in, since
  // owner="me" would 401) — recipes/loading/hasMore all read as empty/settled.
  enabled?: boolean;
}

interface UseInfiniteRecipesResult {
  recipes: Recipe[];
  loading: boolean;
  error: string | null;
  hasMore: boolean;
  // Attach to a (near-)empty element at the end of the list — loads the next page once it
  // scrolls into view. Safe to attach unconditionally; only render it while hasMore is true.
  sentinelRef: (node: HTMLDivElement | null) => void;
}

// Auto-loads more recipes as a sentinel element scrolls into view. Resets to page 1 whenever the
// filters (category/language/owner/onlyPublic/enabled) change.
export function useInfiniteRecipes({
  categoryId,
  language,
  owner,
  onlyPublic,
  favoritesOnly,
  enabled = true,
}: UseInfiniteRecipesParams): UseInfiniteRecipesResult {
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);
  const loadingRef = useRef(enabled);

  useEffect(() => {
    if (!enabled) {
      setRecipes([]);
      setTotal(0);
      setLoading(false);
      loadingRef.current = false;
      return;
    }

    let cancelled = false;
    setError(null);
    setLoading(true);
    loadingRef.current = true;

    api
      .listRecipesPage({
        categoryId,
        language,
        owner,
        onlyPublic,
        favoritesOnly,
        limit: PAGE_SIZE,
        offset: 0,
      })
      .then(({ items, total: newTotal }) => {
        if (cancelled) return;
        setRecipes(items);
        setTotal(newTotal);
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
          loadingRef.current = false;
        }
      });

    return () => {
      cancelled = true;
    };
  }, [categoryId, language, owner, onlyPublic, favoritesOnly, enabled]);

  const hasMore = total !== null && recipes.length < total;

  const loadMore = useCallback(() => {
    if (!enabled || loadingRef.current || !hasMore) return;
    loadingRef.current = true;
    setLoading(true);
    api
      .listRecipesPage({
        categoryId,
        language,
        owner,
        onlyPublic,
        favoritesOnly,
        limit: PAGE_SIZE,
        offset: recipes.length,
      })
      .then(({ items, total: newTotal }) => {
        setRecipes((prev) => [...prev, ...items]);
        setTotal(newTotal);
      })
      .catch((e) => setError(String(e)))
      .finally(() => {
        loadingRef.current = false;
        setLoading(false);
      });
  }, [categoryId, language, owner, onlyPublic, favoritesOnly, enabled, hasMore, recipes.length]);

  const observerRef = useRef<IntersectionObserver | null>(null);
  const sentinelRef = useCallback(
    (node: HTMLDivElement | null) => {
      observerRef.current?.disconnect();
      if (!node) return;
      observerRef.current = new IntersectionObserver(
        (entries) => {
          if (entries[0]?.isIntersecting) loadMore();
        },
        // Generous on purpose: IntersectionObserver only samples periodically, so a fast fling
        // can move the sentinel from "way below the viewport" to "way above it" between two
        // samples without ever registering as intersecting under a small margin — the load
        // silently never fires. A ~1.5-screen trigger zone makes that far less likely.
        { rootMargin: "1200px" }
      );
      observerRef.current.observe(node);
    },
    [loadMore]
  );

  return { recipes, loading, error, hasMore, sentinelRef };
}

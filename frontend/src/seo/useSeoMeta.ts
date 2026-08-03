import { useEffect } from "react";

interface SeoMetaOptions {
  title: string;
  description?: string;
  image?: string;
  canonical?: string;
  hreflangAlternates?: Record<string, string>;
  // Recipes that aren't publicly visible (private, or shared-but-pending-approval) must never
  // signal "index me" — even though their owner can still view the page. See
  // routers/recipes.py's visibility rule; this is the frontend half of the same guarantee.
  noindex?: boolean;
}

function upsertMeta(attr: "name" | "property", key: string, content: string): void {
  const selector = `meta[${attr}="${key}"]`;
  let el = document.head.querySelector<HTMLMetaElement>(selector);
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute(attr, key);
    el.setAttribute("data-seo-managed", "true");
    document.head.appendChild(el);
  }
  el.setAttribute("content", content);
}

function replaceManagedLinks(hreflangAlternates: Record<string, string> | undefined, canonical: string | undefined): void {
  document.head.querySelectorAll('link[data-seo-managed="true"]').forEach((el) => el.remove());

  if (canonical) {
    const link = document.createElement("link");
    link.rel = "canonical";
    link.href = canonical;
    link.setAttribute("data-seo-managed", "true");
    document.head.appendChild(link);
  }
  for (const [lang, href] of Object.entries(hreflangAlternates ?? {})) {
    const link = document.createElement("link");
    link.rel = "alternate";
    link.hreflang = lang;
    link.href = href;
    link.setAttribute("data-seo-managed", "true");
    document.head.appendChild(link);
  }
}

// Imperative DOM management rather than a library (react-helmet-async etc.): this app has no
// SSR, so a library's main value-add (streaming tags to the server-rendered <head>) doesn't
// apply here, and this keeps the bundle smaller. Tags are upserted by a stable selector so
// repeated calls (e.g. navigating between two recipes) update in place instead of piling up.
export function useSeoMeta(options: SeoMetaOptions): void {
  const { title, description, image, canonical, hreflangAlternates, noindex } = options;
  const hreflangKey = JSON.stringify(hreflangAlternates ?? {});

  useEffect(() => {
    document.title = title;

    if (description) upsertMeta("name", "description", description);
    upsertMeta("name", "robots", noindex ? "noindex,nofollow" : "index,follow");

    upsertMeta("property", "og:title", title);
    if (description) upsertMeta("property", "og:description", description);
    if (image) upsertMeta("property", "og:image", image);
    upsertMeta("property", "og:type", "website");

    replaceManagedLinks(hreflangAlternates, canonical);
    // Deliberately no cleanup/restore-on-unmount: the next page's own useSeoMeta call overwrites
    // these same managed tags, and there's always exactly one route rendered at a time.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [title, description, image, canonical, hreflangKey, noindex]);
}

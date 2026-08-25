// Client-side equivalent of the backend's AND-substring title search (see
// api/app/routers/recipes.py's list_recipes and its _unaccent_lower helper) — every word in the
// query must appear somewhere in the title, in any order, case- and diacritic-insensitively, so
// "briose" matches "Brioșe" and a query typed with diacritics still matches a plain-ASCII title.
function foldDiacritics(value: string): string {
  // U+0300-U+036F is the Unicode "Combining Diacritical Marks" block — what NFKD decomposes an
  // accented letter into (base letter + one of these), so stripping the block folds ș/ț/ă/â/î/etc.
  // down to their plain-ASCII base letters.
  return value.normalize("NFKD").replace(/[\u0300-\u036f]/g, "");
}

export function matchesSearchWords(title: string, query: string): boolean {
  const haystack = foldDiacritics(title.toLowerCase());
  return foldDiacritics(query.trim().toLowerCase())
    .split(/\s+/)
    .filter(Boolean)
    .every((word) => haystack.includes(word));
}

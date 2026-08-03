// Kept in sync by hand with api/app/recipe_sections.py and worker/app/recipe_sections.py.
//
// A recipe's ingredients/steps are flat string lists. A sub-group label (e.g. "For the cake:")
// is just another entry in the same list, marked with this prefix so the frontend can render it
// as a sub-heading instead of a bullet/numbered step.
export const SECTION_HEADER_PREFIX = "### ";

export function isSectionHeader(line: string): boolean {
  return line.startsWith(SECTION_HEADER_PREFIX);
}

export function stripSectionHeader(line: string): string {
  return isSectionHeader(line) ? line.slice(SECTION_HEADER_PREFIX.length) : line;
}

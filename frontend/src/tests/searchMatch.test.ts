import { describe, expect, it } from "vitest";
import { matchesSearchWords } from "../ui/searchMatch";

describe("matchesSearchWords", () => {
  it("matches a case-insensitive substring", () => {
    expect(matchesSearchWords("Chocolate Cake", "CHOC")).toBe(true);
    expect(matchesSearchWords("Chocolate Cake", "xyz")).toBe(false);
  });

  it("requires every word, in any order", () => {
    expect(matchesSearchWords("Soup with Chicken", "chicken soup")).toBe(true);
    expect(matchesSearchWords("Chicken Wings", "chicken soup")).toBe(false);
  });

  it("matches regardless of which side has diacritics", () => {
    expect(matchesSearchWords("Brioșe cu dovleac", "briose")).toBe(true);
    expect(matchesSearchWords("Tocanita simpla de vinete", "tocăniță")).toBe(true);
  });
});

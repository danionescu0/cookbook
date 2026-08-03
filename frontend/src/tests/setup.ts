import "@testing-library/jest-dom/vitest";
import { beforeEach } from "vitest";
import { LANGUAGE_STORAGE_KEY } from "../i18n/LanguageContext";
import { installIntersectionObserverMock } from "./testUtils/intersectionObserverMock";

// Existing tests were written assuming English strings; default to it here so component tests
// don't need every text assertion translated. Romanian-default/switching behavior itself is
// covered separately in LanguageContext.test.tsx.
beforeEach(() => {
  window.localStorage.setItem(LANGUAGE_STORAGE_KEY, "en");
  // jsdom has no IntersectionObserver at all — anything rendering useInfiniteRecipes's sentinel
  // (RecipeBrowser) would throw without this. See testUtils/intersectionObserverMock.ts.
  installIntersectionObserverMock();
});

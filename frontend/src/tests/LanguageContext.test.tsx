import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { LANGUAGE_STORAGE_KEY, LanguageProvider, useLanguage } from "../i18n/LanguageContext";

function Consumer() {
  const { language, setLanguage, t } = useLanguage();
  return (
    <div>
      <span data-testid="language">{language}</span>
      <span data-testid="heading">{t.browser.heading}</span>
      <button type="button" onClick={() => setLanguage("en")}>
        switch to en
      </button>
    </div>
  );
}

function renderConsumer() {
  return render(
    <LanguageProvider>
      <Consumer />
    </LanguageProvider>
  );
}

beforeEach(() => {
  window.localStorage.clear();
});

describe("LanguageProvider", () => {
  it("defaults to Romanian when nothing is stored", () => {
    renderConsumer();

    expect(screen.getByTestId("language")).toHaveTextContent("ro");
    expect(screen.getByTestId("heading")).toHaveTextContent("Rețete");
  });

  it("reads a previously stored language", () => {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, "en");

    renderConsumer();

    expect(screen.getByTestId("language")).toHaveTextContent("en");
  });

  it("switching language updates state, translations, and localStorage", async () => {
    const user = userEvent.setup();
    renderConsumer();

    await user.click(screen.getByRole("button", { name: "switch to en" }));

    expect(screen.getByTestId("language")).toHaveTextContent("en");
    expect(screen.getByTestId("heading")).toHaveTextContent("Recipes");
    expect(window.localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe("en");
  });
});

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RecipeBrowser } from "../frontoffice/RecipeBrowser";
import { LanguageProvider } from "../i18n/LanguageContext";
import { api } from "../api/client";
import type { Category, Recipe } from "../types";

vi.mock("../api/client", () => ({
  api: {
    listCategories: vi.fn(),
    listRecipes: vi.fn(),
  },
  BASE_URL: "http://localhost:8000",
}));

const mockedApi = vi.mocked(api);

const desserts: Category = { id: 1, name: "Desserts", slug: "desserts" };
const mains: Category = { id: 2, name: "Mains", slug: "mains" };

const approvedCake: Recipe = {
  id: 1,
  title: "Cake",
  description: "A rich chocolate cake.",
  ingredients: ["flour"],
  steps: ["bake"],
  tips: [],
  images: ["/images/cake.jpg"],
  language: "en",
  category_id: 1,
  source_url: null,
  status: "approved",
  added_at: "2026-07-23T00:00:00Z",
  approved_at: "2026-07-23T00:00:00Z",
  available_languages: ["en"],
};
const unapprovedSoup: Recipe = {
  ...approvedCake,
  id: 2,
  title: "Soup",
  status: "unapproved",
  approved_at: null,
};

beforeEach(() => {
  vi.resetAllMocks();
  mockedApi.listCategories.mockResolvedValue([desserts, mains]);
  mockedApi.listRecipes.mockResolvedValue([approvedCake, unapprovedSoup]);
});

function renderBrowser() {
  return render(
    <LanguageProvider>
      <MemoryRouter>
        <RecipeBrowser />
      </MemoryRouter>
    </LanguageProvider>
  );
}

describe("RecipeBrowser", () => {
  it("only shows approved recipes", async () => {
    renderBrowser();

    expect(await screen.findByText("Cake")).toBeInTheDocument();
    expect(screen.queryByText("Soup")).not.toBeInTheDocument();
  });

  it("links each recipe card to its detail page", async () => {
    renderBrowser();

    const link = (await screen.findByText("Cake")).closest("a");
    expect(link).toHaveAttribute("href", "/recipes/1");
  });

  it("filters by category when a pill is clicked", async () => {
    const user = userEvent.setup();
    renderBrowser();
    await screen.findByText("Cake");

    await user.click(screen.getByRole("button", { name: "Mains" }));

    await waitFor(() => expect(mockedApi.listRecipes).toHaveBeenCalledWith(2, "en"));
  });
});

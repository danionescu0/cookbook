import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { NutritionPanel } from "../frontoffice/NutritionPanel";
import { LanguageProvider } from "../i18n/LanguageContext";
import type { Nutrition } from "../types";

function renderPanel(nutrition: Nutrition) {
  return render(
    <LanguageProvider>
      <NutritionPanel nutrition={nutrition} />
    </LanguageProvider>
  );
}

const doneWithServings: Nutrition = {
  status: "done",
  error: null,
  estimated_servings: 4,
  total_grams: 1900,
  totals: { calories: 800, protein_g: 40, carbs_g: 60, sugars_g: 12, fat_g: 20 },
  per_serving: { calories: 200, protein_g: 10, carbs_g: 15, sugars_g: 3, fat_g: 5 },
  per_ingredient: [],
};

describe("NutritionPanel", () => {
  it("renders per-serving values and the servings estimate when both are known", async () => {
    renderPanel(doneWithServings);

    expect(await screen.findByText("Nutrition")).toBeInTheDocument();
    expect(screen.getByText("Serves ~4")).toBeInTheDocument();
    expect(screen.getByText("~1.9 kg total")).toBeInTheDocument();
    expect(screen.getByText("200")).toBeInTheDocument(); // per-serving calories
    expect(screen.getByText("10")).toBeInTheDocument(); // per-serving protein
    expect(screen.queryByText("800")).not.toBeInTheDocument(); // whole-recipe total not shown
    expect(screen.getByText("Per serving")).toBeInTheDocument();
  });

  it("shows the total weight in grams under 1kg", async () => {
    renderPanel({ ...doneWithServings, total_grams: 850 });
    expect(await screen.findByText("~850 g total")).toBeInTheDocument();
  });

  it("doesn't show a total weight badge when total_grams is unknown", async () => {
    renderPanel({ ...doneWithServings, total_grams: null });
    await screen.findByText("Nutrition"); // panel rendered
    expect(screen.queryByText(/total$/)).not.toBeInTheDocument();
  });

  it("falls back to whole-recipe totals when there's no servings estimate", async () => {
    const withoutServings: Nutrition = {
      ...doneWithServings,
      estimated_servings: null,
      per_serving: null,
    };

    renderPanel(withoutServings);

    expect(await screen.findByText("800")).toBeInTheDocument();
    expect(screen.getByText("Whole recipe")).toBeInTheDocument();
    expect(screen.queryByText("Serves ~4")).not.toBeInTheDocument();
  });

  it("renders nothing when nutrition hasn't been enriched yet", () => {
    const notEnriched: Nutrition = {
      status: "not_enriched",
      error: null,
      estimated_servings: null,
      total_grams: null,
      totals: null,
      per_serving: null,
      per_ingredient: [],
    };

    const { container } = renderPanel(notEnriched);

    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing while a job is still queued or processing", () => {
    const processing: Nutrition = {
      status: "processing",
      error: null,
      estimated_servings: null,
      total_grams: null,
      totals: null,
      per_serving: null,
      per_ingredient: [],
    };

    const { container } = renderPanel(processing);

    expect(container).toBeEmptyDOMElement();
  });
});

import { useLanguage } from "../i18n/LanguageContext";
import {
  DropletIcon,
  DrumstickIcon,
  FlameIcon,
  ScaleIcon,
  ServingsIcon,
  SugarCubesIcon,
  WheatIcon,
} from "../ui/nutritionIcons";
import type { Nutrition } from "../types";

interface NutritionPanelProps {
  nutrition: Nutrition;
}

// "g" isn't meaningfully more readable than "kg" for a several-kilogram pot of soup — same
// threshold a kitchen scale's own display would switch at.
function formatWeight(grams: number): string {
  return grams >= 1000 ? `${(grams / 1000).toFixed(1)} kg` : `${Math.round(grams)} g`;
}

export function NutritionPanel({ nutrition }: NutritionPanelProps) {
  const { t } = useLanguage();

  if (nutrition.status !== "done" || !nutrition.totals) {
    return null;
  }

  // Per serving is the more meaningful number for a reader deciding what to eat; total-recipe
  // figures are shown as a fallback only when there's no servings estimate to divide by.
  const values = nutrition.per_serving ?? nutrition.totals;
  const isPerServing = nutrition.per_serving !== null;

  const tiles = [
    { Icon: FlameIcon, value: Math.round(values.calories), unit: "kcal", label: t.nutrition.calories },
    { Icon: DrumstickIcon, value: Math.round(values.protein_g), unit: "g", label: t.nutrition.protein },
    { Icon: WheatIcon, value: Math.round(values.carbs_g), unit: "g", label: t.nutrition.carbs },
    { Icon: SugarCubesIcon, value: Math.round(values.sugars_g), unit: "g", label: t.nutrition.sugars },
    { Icon: DropletIcon, value: Math.round(values.fat_g), unit: "g", label: t.nutrition.fat },
  ];

  return (
    <section
      aria-labelledby="nutrition-heading"
      className="mt-8 rounded-lg bg-cream-card p-5 ring-1 ring-black/5"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="nutrition-heading" className="font-serif text-xl font-semibold text-ink">
          {t.nutrition.heading}
        </h2>
        <div className="flex flex-wrap items-center gap-2">
          {nutrition.estimated_servings && (
            <span className="flex items-center gap-1.5 rounded-full bg-olive-light px-3 py-1 text-sm text-ink/80">
              <ServingsIcon className="h-4 w-4 text-olive" />
              {t.nutrition.servesEstimate.replace("{count}", String(nutrition.estimated_servings))}
            </span>
          )}
          {nutrition.total_grams && (
            <span className="flex items-center gap-1.5 rounded-full bg-olive-light px-3 py-1 text-sm text-ink/80">
              <ScaleIcon className="h-4 w-4 text-olive" />
              {t.nutrition.totalWeight.replace("{amount}", formatWeight(nutrition.total_grams))}
            </span>
          )}
        </div>
      </div>

      <p className="mt-1 text-xs text-ink/50">
        <span>{isPerServing ? t.nutrition.perServing : t.nutrition.wholeRecipe}</span>
        {" · "}
        <span>{t.nutrition.estimateNote}</span>
      </p>

      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-5">
        {tiles.map(({ Icon, value, unit, label }) => (
          <div
            key={label}
            className="flex flex-col items-center gap-1 rounded-md bg-white/70 p-3 text-center ring-1 ring-black/5"
          >
            <Icon className="h-6 w-6 text-terracotta" />
            <span className="font-serif text-xl font-semibold text-ink">
              {value}
              <span className="ml-0.5 text-xs font-normal text-ink/50">{unit}</span>
            </span>
            <span className="text-xs text-ink/60">{label}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

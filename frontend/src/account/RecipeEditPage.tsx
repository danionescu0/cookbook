import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, BASE_URL } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useLanguage } from "../i18n/LanguageContext";
import { primaryButton, secondaryButton } from "../ui/buttonStyles";
import type { Category, Recipe } from "../types";

function toLines(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

interface EditForm {
  title: string;
  description: string;
  ingredients: string;
  steps: string;
  tips: string;
  categoryId: number | "";
  images: string[];
}

function toEditForm(recipe: Recipe): EditForm {
  return {
    title: recipe.title,
    description: recipe.description,
    ingredients: recipe.ingredients.join("\n"),
    steps: recipe.steps.join("\n"),
    tips: recipe.tips.join("\n"),
    categoryId: recipe.category_id,
    images: recipe.images,
  };
}

const inputClasses =
  "rounded-md border border-olive/30 bg-white px-3 py-2 text-sm text-ink focus:border-terracotta focus:outline-none";

// The account page's own recipe editor — RecipeManager.tsx has a near-identical inline form, but
// that one is admin-only (approve/reparse/delete alongside it) and lives inside the back office.
// This page is what "Edit" from the post-import review panel (and, more generally, any owner
// wanting to fix their own recipe) actually opens.
export function RecipeEditPage() {
  const { id } = useParams<{ id: string }>();
  const { language, t } = useLanguage();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [form, setForm] = useState<EditForm | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploadingImage, setUploadingImage] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!id) return;
    api
      .getRecipe(Number(id), language)
      .then((r) => {
        setRecipe(r);
        setForm(toEditForm(r));
      })
      .catch((e) => setError(String(e)));
    api.listCategories().then(setCategories).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (error) {
    return (
      <div>
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
        <Link to="/import" className="mt-3 inline-block text-sm text-terracotta hover:underline">
          {t.account.backToAccount}
        </Link>
      </div>
    );
  }

  if (!recipe || !form) {
    return <p className="text-ink/60">{t.detail.loading}</p>;
  }

  const canEdit = user?.is_admin || user?.id === recipe.owner_user_id;
  if (!canEdit) {
    return (
      <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
        {t.backoffice.accessDenied}
      </p>
    );
  }

  const uploadImages = async (files: FileList | File[]) => {
    setError(null);
    setUploadingImage(true);
    try {
      for (const file of Array.from(files)) {
        if (!file.type.startsWith("image/")) continue;
        const { url } = await api.uploadImage(file);
        setForm((current) => (current ? { ...current, images: [...current.images, url] } : current));
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setUploadingImage(false);
    }
  };

  const removeImage = (url: string) => {
    setForm((current) =>
      current ? { ...current, images: current.images.filter((i) => i !== url) } : current
    );
  };

  const handleSave = async (event: React.FormEvent) => {
    event.preventDefault();
    if (form.categoryId === "") return;
    setError(null);
    setSaving(true);
    try {
      await api.updateRecipe(
        recipe.id,
        {
          category_id: form.categoryId,
          images: form.images,
          translation: {
            title: form.title.trim(),
            description: form.description,
            ingredients: toLines(form.ingredients),
            steps: toLines(form.steps),
            tips: toLines(form.tips),
          },
        },
        language
      );
      navigate("/import");
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-lg bg-cream-card p-5 ring-1 ring-black/5">
      <Link to="/import" className="text-sm text-terracotta hover:underline">
        {t.account.backToAccount}
      </Link>
      <h2 className="mt-2 font-serif text-2xl font-semibold text-ink">
        {t.account.editRecipeHeading}
      </h2>

      {error && (
        <p role="alert" className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      <form onSubmit={handleSave} className="mt-4 flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-sm font-medium text-ink/70">{t.recipeManager.titleLabel}</label>
          <input
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            className={inputClasses}
          />
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-sm font-medium text-ink/70">{t.recipeManager.categoryLabel}</label>
          <select
            value={form.categoryId}
            onChange={(e) => setForm({ ...form, categoryId: Number(e.target.value) })}
            className={inputClasses}
          >
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-sm font-medium text-ink/70">
            {t.recipeManager.descriptionLabel}
          </label>
          <textarea
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            rows={2}
            className={inputClasses}
          />
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-sm font-medium text-ink/70">
            {t.recipeManager.ingredientsLabel}
          </label>
          <textarea
            value={form.ingredients}
            onChange={(e) => setForm({ ...form, ingredients: e.target.value })}
            rows={4}
            className={inputClasses}
          />
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-sm font-medium text-ink/70">{t.recipeManager.stepsLabel}</label>
          <textarea
            value={form.steps}
            onChange={(e) => setForm({ ...form, steps: e.target.value })}
            rows={4}
            className={inputClasses}
          />
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-sm font-medium text-ink/70">{t.recipeManager.tipsLabel}</label>
          <textarea
            value={form.tips}
            onChange={(e) => setForm({ ...form, tips: e.target.value })}
            rows={2}
            className={inputClasses}
          />
        </div>

        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium text-ink/70">{t.recipeManager.imagesLabel}</label>
          <div className="flex flex-wrap gap-3">
            {form.images.map((image) => (
              <div key={image} className="relative">
                <img src={`${BASE_URL}${image}`} alt="" className="h-24 w-24 rounded-md object-cover" />
                <button
                  type="button"
                  onClick={() => removeImage(image)}
                  aria-label={t.recipeManager.removeImage}
                  className="absolute -right-2 -top-2 flex h-6 w-6 items-center justify-center rounded-full bg-terracotta text-sm text-white shadow"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
          <div
            onPaste={(e) => {
              const files = Array.from(e.clipboardData.files);
              if (files.length > 0) uploadImages(files);
            }}
          >
            <input
              type="file"
              accept="image/*"
              multiple
              disabled={uploadingImage}
              onChange={(e) => e.target.files && uploadImages(e.target.files)}
              className="text-sm text-ink/70"
            />
            <p className="mt-1 text-xs text-ink/50">{t.recipeManager.pasteImageHint}</p>
          </div>
        </div>

        <div className="flex gap-2">
          <button type="submit" disabled={saving} className={primaryButton}>
            {t.recipeManager.save}
          </button>
          <Link to="/import" className={secondaryButton}>
            {t.recipeManager.cancel}
          </Link>
        </div>
      </form>
    </div>
  );
}

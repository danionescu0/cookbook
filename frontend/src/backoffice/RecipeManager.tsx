import { useEffect, useState } from "react";
import { api, BASE_URL } from "../api/client";
import { useLanguage } from "../i18n/LanguageContext";
import { dangerButton, primaryButton, secondaryButton } from "../ui/buttonStyles";
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

export function RecipeManager() {
  const { language, t } = useLanguage();
  const [categories, setCategories] = useState<Category[]>([]);
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [title, setTitle] = useState("");
  const [categoryId, setCategoryId] = useState<number | "">("");
  const [ingredients, setIngredients] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [previewId, setPreviewId] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<EditForm | null>(null);
  const [uploadingImage, setUploadingImage] = useState(false);

  const reload = () =>
    api.listRecipes(undefined, language).then(setRecipes).catch((e) => setError(String(e)));

  useEffect(() => {
    api.listCategories().then(setCategories).catch((e) => setError(String(e)));
    reload();
  }, [language]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!title.trim() || categoryId === "") return;
    setError(null);
    try {
      await api.createRecipe({
        title: title.trim(),
        description: "",
        ingredients: toLines(ingredients),
        steps: [],
        tips: [],
        images: [],
        language,
        category_id: categoryId,
      });
      setTitle("");
      setIngredients("");
      await reload();
    } catch (e) {
      setError(String(e));
    }
  };

  const handleDelete = async (id: number) => {
    setError(null);
    try {
      await api.deleteRecipe(id);
      await reload();
    } catch (e) {
      setError(String(e));
    }
  };

  const handleApprove = async (id: number) => {
    setError(null);
    try {
      await api.approveRecipe(id);
      await reload();
    } catch (e) {
      setError(String(e));
    }
  };

  const startEdit = (recipe: Recipe) => {
    setPreviewId(null);
    setEditingId(recipe.id);
    setEditForm(toEditForm(recipe));
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditForm(null);
  };

  const uploadImages = async (files: FileList | File[]) => {
    setError(null);
    setUploadingImage(true);
    try {
      for (const file of Array.from(files)) {
        if (!file.type.startsWith("image/")) continue;
        const { url } = await api.uploadImage(file);
        setEditForm((form) => (form ? { ...form, images: [...form.images, url] } : form));
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setUploadingImage(false);
    }
  };

  const removeImage = (url: string) => {
    setEditForm((form) => (form ? { ...form, images: form.images.filter((i) => i !== url) } : form));
  };

  const handleSaveEdit = async () => {
    if (!editForm || editingId === null || editForm.categoryId === "") return;
    setError(null);
    try {
      await api.updateRecipe(
        editingId,
        {
          category_id: editForm.categoryId,
          images: editForm.images,
          translation: {
            title: editForm.title.trim(),
            description: editForm.description,
            ingredients: toLines(editForm.ingredients),
            steps: toLines(editForm.steps),
            tips: toLines(editForm.tips),
          },
        },
        language
      );
      cancelEdit();
      await reload();
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <section
      aria-labelledby="recipes-heading"
      className="rounded-lg bg-cream-card p-5 ring-1 ring-black/5"
    >
      <h2 id="recipes-heading" className="font-serif text-2xl font-semibold text-ink">
        {t.recipeManager.heading}
      </h2>

      <form onSubmit={handleSubmit} className="mt-4 flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label htmlFor="recipe-title" className="text-sm font-medium text-ink/70">
            {t.recipeManager.titleLabel}
          </label>
          <input
            id="recipe-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="rounded-md border border-olive/30 bg-white px-3 py-2 text-sm text-ink focus:border-terracotta focus:outline-none"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="recipe-category" className="text-sm font-medium text-ink/70">
            {t.recipeManager.categoryLabel}
          </label>
          <select
            id="recipe-category"
            value={categoryId}
            onChange={(e) => setCategoryId(e.target.value ? Number(e.target.value) : "")}
            className="rounded-md border border-olive/30 bg-white px-3 py-2 text-sm text-ink focus:border-terracotta focus:outline-none"
          >
            <option value="">{t.recipeManager.categoryPlaceholder}</option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
        </div>

        <div className="flex min-w-48 flex-1 flex-col gap-1">
          <label htmlFor="recipe-ingredients" className="text-sm font-medium text-ink/70">
            {t.recipeManager.ingredientsLabel}
          </label>
          <textarea
            id="recipe-ingredients"
            value={ingredients}
            onChange={(e) => setIngredients(e.target.value)}
            rows={2}
            className="rounded-md border border-olive/30 bg-white px-3 py-2 text-sm text-ink focus:border-terracotta focus:outline-none"
          />
        </div>

        <button type="submit" className={primaryButton}>
          {t.recipeManager.add}
        </button>
      </form>

      {error && (
        <p role="alert" className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      <ul className="mt-5 divide-y divide-olive-light">
        {recipes.map((recipe) => (
          <li key={recipe.id} className="py-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-ink">
                {recipe.title} <em className="text-sm text-ink/50 not-italic">({recipe.status})</em>
              </span>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => setPreviewId(previewId === recipe.id ? null : recipe.id)}
                  className={secondaryButton}
                >
                  {previewId === recipe.id ? t.recipeManager.hidePreview : t.recipeManager.preview}
                </button>
                <button
                  type="button"
                  onClick={() => (editingId === recipe.id ? cancelEdit() : startEdit(recipe))}
                  className={secondaryButton}
                >
                  {editingId === recipe.id ? t.recipeManager.cancel : t.recipeManager.edit}
                </button>
                {recipe.status === "unapproved" && (
                  <button
                    type="button"
                    onClick={() => handleApprove(recipe.id)}
                    className={primaryButton}
                  >
                    {t.recipeManager.approve}
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => handleDelete(recipe.id)}
                  className={dangerButton}
                >
                  {t.recipeManager.delete}
                </button>
              </div>
            </div>

            {editingId === recipe.id && editForm && (
              <div className="mt-3 flex flex-col gap-3 rounded-md bg-olive-light p-4">
                <div className="flex flex-col gap-1">
                  <label className="text-sm font-medium text-ink/70">
                    {t.recipeManager.titleLabel}
                  </label>
                  <input
                    value={editForm.title}
                    onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                    className="rounded-md border border-olive/30 bg-white px-3 py-2 text-sm text-ink focus:border-terracotta focus:outline-none"
                  />
                </div>

                <div className="flex flex-col gap-1">
                  <label className="text-sm font-medium text-ink/70">
                    {t.recipeManager.categoryLabel}
                  </label>
                  <select
                    value={editForm.categoryId}
                    onChange={(e) =>
                      setEditForm({ ...editForm, categoryId: Number(e.target.value) })
                    }
                    className="rounded-md border border-olive/30 bg-white px-3 py-2 text-sm text-ink focus:border-terracotta focus:outline-none"
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
                    value={editForm.description}
                    onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                    rows={2}
                    className="rounded-md border border-olive/30 bg-white px-3 py-2 text-sm text-ink focus:border-terracotta focus:outline-none"
                  />
                </div>

                <div className="flex flex-col gap-1">
                  <label className="text-sm font-medium text-ink/70">
                    {t.recipeManager.ingredientsLabel}
                  </label>
                  <textarea
                    value={editForm.ingredients}
                    onChange={(e) => setEditForm({ ...editForm, ingredients: e.target.value })}
                    rows={3}
                    className="rounded-md border border-olive/30 bg-white px-3 py-2 text-sm text-ink focus:border-terracotta focus:outline-none"
                  />
                </div>

                <div className="flex flex-col gap-1">
                  <label className="text-sm font-medium text-ink/70">
                    {t.recipeManager.stepsLabel}
                  </label>
                  <textarea
                    value={editForm.steps}
                    onChange={(e) => setEditForm({ ...editForm, steps: e.target.value })}
                    rows={3}
                    className="rounded-md border border-olive/30 bg-white px-3 py-2 text-sm text-ink focus:border-terracotta focus:outline-none"
                  />
                </div>

                <div className="flex flex-col gap-1">
                  <label className="text-sm font-medium text-ink/70">
                    {t.recipeManager.tipsLabel}
                  </label>
                  <textarea
                    value={editForm.tips}
                    onChange={(e) => setEditForm({ ...editForm, tips: e.target.value })}
                    rows={2}
                    className="rounded-md border border-olive/30 bg-white px-3 py-2 text-sm text-ink focus:border-terracotta focus:outline-none"
                  />
                </div>

                <div className="flex flex-col gap-2">
                  <label className="text-sm font-medium text-ink/70">
                    {t.recipeManager.imagesLabel}
                  </label>
                  <div className="flex flex-wrap gap-3">
                    {editForm.images.map((image) => (
                      <div key={image} className="relative">
                        <img
                          src={`${BASE_URL}${image}`}
                          alt=""
                          className="h-24 w-24 rounded-md object-cover"
                        />
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
                  <button type="button" onClick={handleSaveEdit} className={primaryButton}>
                    {t.recipeManager.save}
                  </button>
                  <button type="button" onClick={cancelEdit} className={secondaryButton}>
                    {t.recipeManager.cancel}
                  </button>
                </div>
              </div>
            )}

            {previewId === recipe.id && (
              <div className="mt-3 rounded-md bg-olive-light p-4">
                {recipe.images.map((image) => (
                  <img
                    key={image}
                    src={`${BASE_URL}${image}`}
                    alt={recipe.title}
                    className="mb-3 h-40 w-40 rounded-md object-cover"
                  />
                ))}
                {recipe.description && <p className="text-ink/80">{recipe.description}</p>}
                {recipe.ingredients.length > 0 && (
                  <>
                    <h3 className="mt-3 font-serif text-lg font-semibold text-ink">
                      {t.recipeManager.ingredients}
                    </h3>
                    <ul className="mt-1 list-inside list-disc text-ink/80">
                      {recipe.ingredients.map((ingredient) => (
                        <li key={ingredient}>{ingredient}</li>
                      ))}
                    </ul>
                  </>
                )}
                {recipe.steps.length > 0 && (
                  <>
                    <h3 className="mt-3 font-serif text-lg font-semibold text-ink">
                      {t.recipeManager.steps}
                    </h3>
                    <ol className="mt-1 list-inside list-decimal text-ink/80">
                      {recipe.steps.map((step) => (
                        <li key={step}>{step}</li>
                      ))}
                    </ol>
                  </>
                )}
                {recipe.tips.length > 0 && (
                  <>
                    <h3 className="mt-3 font-serif text-lg font-semibold text-ink">
                      {t.recipeManager.tips}
                    </h3>
                    <ul className="mt-1 list-inside list-disc text-ink/80">
                      {recipe.tips.map((tip) => (
                        <li key={tip}>{tip}</li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, BASE_URL } from "../api/client";
import { useLanguage } from "../i18n/LanguageContext";
import { primaryButton } from "../ui/buttonStyles";
import type { Category } from "../types";

const inputClasses =
  "rounded-md border border-olive/30 bg-white px-3 py-2 text-sm text-ink focus:border-terracotta focus:outline-none";

function toLines(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

export function RecipeSubmitForm() {
  const { language, t } = useLanguage();
  const [categories, setCategories] = useState<Category[]>([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [categoryId, setCategoryId] = useState<number | "">("");
  const [ingredients, setIngredients] = useState("");
  const [steps, setSteps] = useState("");
  const [tips, setTips] = useState("");
  const [images, setImages] = useState<string[]>([]);
  const [isShared, setIsShared] = useState(false);
  const [uploadingImage, setUploadingImage] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  // Distinguishes "saved, only you can see it" from "sent for review before it's public" —
  // depends on whether sharing was requested and, if so, whether it needed moderation (an
  // admin's own shared recipes skip that step).
  const [successStatus, setSuccessStatus] = useState<{ shared: boolean; approved: boolean } | null>(
    null
  );

  useEffect(() => {
    api.listCategories().then(setCategories).catch((e) => setError(String(e)));
  }, []);

  const uploadImages = async (files: FileList | File[]) => {
    setError(null);
    setUploadingImage(true);
    try {
      for (const file of Array.from(files)) {
        if (!file.type.startsWith("image/")) continue;
        const { url } = await api.uploadImage(file);
        setImages((current) => [...current, url]);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setUploadingImage(false);
    }
  };

  const removeImage = (url: string) => {
    setImages((current) => current.filter((i) => i !== url));
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!title.trim() || categoryId === "") return;
    setError(null);
    setSubmitting(true);
    try {
      const created = await api.submitRecipe({
        title: title.trim(),
        description,
        ingredients: toLines(ingredients),
        steps: toLines(steps),
        tips: toLines(tips),
        images,
        language,
        category_id: categoryId,
        is_shared: isShared,
      });
      setSuccessStatus({ shared: created.is_shared, approved: created.status === "approved" });
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  };

  if (successStatus) {
    const message =
      successStatus.shared && !successStatus.approved
        ? t.recipeSubmit.successPendingReview
        : successStatus.shared
          ? t.recipeSubmit.successShared
          : t.recipeSubmit.successPrivate;
    return (
      <section className="mx-auto max-w-lg rounded-lg bg-cream-card p-6 ring-1 ring-black/5">
        <h2 className="font-serif text-2xl font-semibold text-ink">{t.recipeSubmit.heading}</h2>
        <p role="status" className="mt-4 rounded-md bg-olive-light px-3 py-2 text-sm text-ink">
          {message}
        </p>
        <Link to="/import" className="mt-4 inline-block text-sm text-terracotta hover:underline">
          {t.recipeSubmit.backLink}
        </Link>
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-lg rounded-lg bg-cream-card p-6 ring-1 ring-black/5">
      <h2 className="font-serif text-2xl font-semibold text-ink">{t.recipeSubmit.heading}</h2>
      <p className="mt-2 text-sm text-ink/70">{t.recipeSubmit.intro}</p>

      <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <label htmlFor="submit-recipe-title" className="text-sm font-medium text-ink/70">
            {t.recipeManager.titleLabel}
          </label>
          <input
            id="submit-recipe-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className={inputClasses}
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="submit-recipe-category" className="text-sm font-medium text-ink/70">
            {t.recipeManager.categoryLabel}
          </label>
          <select
            id="submit-recipe-category"
            value={categoryId}
            onChange={(e) => setCategoryId(e.target.value ? Number(e.target.value) : "")}
            className={inputClasses}
          >
            <option value="">{t.recipeManager.categoryPlaceholder}</option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="submit-recipe-description" className="text-sm font-medium text-ink/70">
            {t.recipeManager.descriptionLabel}
          </label>
          <textarea
            id="submit-recipe-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            className={inputClasses}
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="submit-recipe-ingredients" className="text-sm font-medium text-ink/70">
            {t.recipeManager.ingredientsLabel}
          </label>
          <textarea
            id="submit-recipe-ingredients"
            value={ingredients}
            onChange={(e) => setIngredients(e.target.value)}
            rows={4}
            className={inputClasses}
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="submit-recipe-steps" className="text-sm font-medium text-ink/70">
            {t.recipeManager.stepsLabel}
          </label>
          <textarea
            id="submit-recipe-steps"
            value={steps}
            onChange={(e) => setSteps(e.target.value)}
            rows={4}
            className={inputClasses}
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="submit-recipe-tips" className="text-sm font-medium text-ink/70">
            {t.recipeManager.tipsLabel}
          </label>
          <textarea
            id="submit-recipe-tips"
            value={tips}
            onChange={(e) => setTips(e.target.value)}
            rows={2}
            className={inputClasses}
          />
        </div>

        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium text-ink/70">{t.recipeManager.imagesLabel}</label>
          <div className="flex flex-wrap gap-3">
            {images.map((image) => (
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

        <label className="flex items-start gap-2 text-sm text-ink">
          <input
            type="checkbox"
            checked={isShared}
            onChange={(e) => setIsShared(e.target.checked)}
            className="mt-0.5"
          />
          <span>
            {t.recipeSubmit.shareLabel}
            <span className="block text-xs text-ink/50">{t.recipeSubmit.shareHint}</span>
          </span>
        </label>

        {error && (
          <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}

        <div>
          <button type="submit" disabled={submitting} className={primaryButton}>
            {t.recipeSubmit.submit}
          </button>
        </div>
      </form>
    </section>
  );
}

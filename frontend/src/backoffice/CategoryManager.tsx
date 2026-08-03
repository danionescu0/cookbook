import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useLanguage } from "../i18n/LanguageContext";
import { dangerButton, primaryButton } from "../ui/buttonStyles";
import { useConfirm } from "../ui/useConfirm";
import type { Category } from "../types";

export function CategoryManager() {
  const { t } = useLanguage();
  const { confirm, confirmDialog } = useConfirm();
  const [categories, setCategories] = useState<Category[]>([]);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const reload = () => api.listCategories().then(setCategories).catch((e) => setError(String(e)));

  useEffect(() => {
    reload();
  }, []);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!name.trim()) return;
    setError(null);
    try {
      await api.createCategory(name.trim());
      setName("");
      await reload();
    } catch (e) {
      setError(String(e));
    }
  };

  const handleDelete = async (id: number) => {
    if (!(await confirm(t.categoryManager.confirmDelete))) return;
    setError(null);
    try {
      await api.deleteCategory(id);
      await reload();
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <section
      aria-labelledby="categories-heading"
      className="rounded-lg bg-cream-card p-5 ring-1 ring-black/5"
    >
      <h2 id="categories-heading" className="font-serif text-2xl font-semibold text-ink">
        {t.categoryManager.heading}
      </h2>

      <form onSubmit={handleSubmit} className="mt-4 flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label htmlFor="category-name" className="text-sm font-medium text-ink/70">
            {t.categoryManager.nameLabel}
          </label>
          <input
            id="category-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t.categoryManager.namePlaceholder}
            className="rounded-md border border-olive/30 bg-white px-3 py-2 text-sm text-ink focus:border-terracotta focus:outline-none"
          />
        </div>
        <button type="submit" className={primaryButton}>
          {t.categoryManager.add}
        </button>
      </form>

      {error && (
        <p role="alert" className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      <ul className="mt-5 divide-y divide-olive-light">
        {categories.map((category) => (
          <li key={category.id} className="flex items-center justify-between py-2">
            <span className="text-ink">{category.name}</span>
            <button
              type="button"
              onClick={() => handleDelete(category.id)}
              className={dangerButton}
            >
              {t.categoryManager.delete}
            </button>
          </li>
        ))}
      </ul>
      {confirmDialog}
    </section>
  );
}

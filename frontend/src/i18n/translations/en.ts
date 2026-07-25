const en = {
  brand: "Cookbook",
  nav: {
    recipes: "Recipes",
    backoffice: "Back office",
  },
  browser: {
    heading: "Recipes",
    subtitle: "Browse by category, or see everything.",
    all: "All",
    empty: "No recipes here yet.",
    noImage: "No image",
  },
  detail: {
    back: "← Back to recipes",
    notPublished: "This recipe isn't published yet.",
    loading: "Loading…",
    ingredients: "Ingredients",
    steps: "Steps",
    tips: "Tips",
  },
  categoryManager: {
    heading: "Categories",
    nameLabel: "Name",
    namePlaceholder: "e.g. Desserts",
    add: "Add category",
    delete: "Delete",
  },
  recipeManager: {
    heading: "Recipes",
    titleLabel: "Title",
    categoryLabel: "Category",
    categoryPlaceholder: "Select a category",
    ingredientsLabel: "Ingredients (one per line)",
    add: "Add recipe",
    preview: "Preview",
    hidePreview: "Hide preview",
    approve: "Approve",
    delete: "Delete",
    ingredients: "Ingredients",
    steps: "Steps",
    tips: "Tips",
  },
  importManager: {
    heading: "Import from URL",
    urlLabel: "Recipe URL",
    categoryLabel: "Category",
    categoryPlaceholder: "Select a category",
    add: "Add",
    approve: "Approve",
    delete: "Delete",
    statuses: {
      pending: "Pending",
      queued: "Queued",
      fetching: "Fetching",
      processing: "Processing",
      done: "Done",
      failed: "Failed",
    },
  },
};

export type Translation = typeof en;

export default en;

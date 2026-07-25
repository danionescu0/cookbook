import type { Translation } from "./en";

// Typed against `Translation` (en's shape) so a missing/extra key is a compile error, not a
// silently-blank string in production.
const ro: Translation = {
  brand: "Cookbook",
  nav: {
    recipes: "Rețete",
    backoffice: "Panou admin",
    logout: "Deconectare",
  },
  login: {
    heading: "Autentificare panou admin",
    usernameLabel: "Utilizator",
    passwordLabel: "Parolă",
    submit: "Conectare",
    error: "Utilizator sau parolă incorecte.",
  },
  browser: {
    heading: "Rețete",
    subtitle: "Răsfoiește după categorie, sau vezi tot.",
    all: "Toate",
    empty: "Încă nu sunt rețete aici.",
    noImage: "Fără imagine",
  },
  detail: {
    back: "← Înapoi la rețete",
    notPublished: "Această rețetă nu este încă publicată.",
    loading: "Se încarcă…",
    ingredients: "Ingrediente",
    steps: "Pași",
    tips: "Sfaturi",
  },
  categoryManager: {
    heading: "Categorii",
    nameLabel: "Nume",
    namePlaceholder: "ex. Deserturi",
    add: "Adaugă categorie",
    delete: "Șterge",
  },
  recipeManager: {
    heading: "Rețete",
    titleLabel: "Titlu",
    categoryLabel: "Categorie",
    categoryPlaceholder: "Alege o categorie",
    ingredientsLabel: "Ingrediente (unul pe linie)",
    add: "Adaugă rețetă",
    preview: "Previzualizare",
    hidePreview: "Ascunde previzualizarea",
    approve: "Aprobă",
    delete: "Șterge",
    ingredients: "Ingrediente",
    steps: "Pași",
    tips: "Sfaturi",
  },
  importManager: {
    heading: "Importă din URL",
    urlLabel: "URL rețetă",
    categoryLabel: "Categorie",
    categoryPlaceholder: "Alege o categorie",
    add: "Adaugă",
    approve: "Aprobă",
    delete: "Șterge",
    statuses: {
      pending: "În așteptare",
      queued: "În coadă",
      fetching: "Se preia",
      processing: "Se procesează",
      done: "Finalizat",
      failed: "Eșuat",
    },
  },
};

export default ro;

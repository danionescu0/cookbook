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
  settingsManager: {
    heading: "Setări",
    supportedLanguagesLabel: "Limbi disponibile",
    supportedLanguagesHelp:
      "Coduri de limbă separate prin virgulă în care site-ul traduce rețetele, ex. ro,en. Adăugarea unui cod aici nu retraduce rețetele deja existente.",
    defaultLanguageLabel: "Limbă implicită",
    defaultLanguageHelp:
      "Afișată atunci când limba vizitatorului nu este disponibilă pentru o rețetă. Trebuie să fie una dintre limbile disponibile de mai sus.",
    adminPasswordLabel: "Parolă panou admin",
    adminPasswordHelp:
      "Parola pentru autentificarea în acest panou admin. Sesiunile deja active rămân conectate până expiră.",
    anthropicApiKeyLabel: "Cheie API Anthropic",
    anthropicApiKeyHelp:
      "Folosită de worker-ul de import pentru a cere lui Claude extragerea și traducerea rețetelor dintr-un URL.",
    secretSetPlaceholder: "Lasă necompletat pentru a păstra valoarea curentă",
    secretUnsetPlaceholder: "Nesetat",
    rateLimitLabel: "Limită import (cereri/minut)",
    rateLimitHelp:
      "Numărul maxim de cereri pe minut pe care worker-ul de import le face către un singur site sursă. Crawl-delay-ul propriu al site-ului din robots.txt, dacă există, are prioritate.",
    scrapeTimeoutLabel: "Timeout preluare (secunde)",
    scrapeTimeoutHelp:
      "Cât timp așteaptă worker-ul de import răspunsul unei pagini sau imagini înainte de a renunța la acea cerere.",
    maxHtmlCharsLabel: "HTML maxim trimis către Claude (caractere)",
    maxHtmlCharsHelp:
      "Paginile de rețete mai lungi decât atât sunt trunchiate înainte de a fi trimise spre extragere.",
    imageMaxDimensionLabel: "Dimensiune maximă imagine (px)",
    imageMaxDimensionHelp:
      "Fotografiile rețetelor sunt redimensionate astfel încât nicio latură să nu depășească acest număr de pixeli înainte de a fi salvate.",
    imageMaxSizeKbLabel: "Dimensiune maximă imagine (KB)",
    imageMaxSizeKbHelp:
      "Fotografiile rețetelor sunt recomprimate până ajung sub această dimensiune, sau până calitatea atinge pragul minim.",
    apply: "Aplică",
    applying: "Se aplică…",
    applied: "Setările au fost aplicate.",
  },
};

export default ro;

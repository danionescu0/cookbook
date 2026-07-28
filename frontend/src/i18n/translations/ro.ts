import type { Translation } from "./en";

// Typed against `Translation` (en's shape) so a missing/extra key is a compile error, not a
// silently-blank string in production.
const ro: Translation = {
  brand: "Cookbook",
  nav: {
    recipes: "Rețete",
    backoffice: "Panou admin",
    logout: "Deconectare",
    backofficeRecipes: "Rețete",
    backofficeSettings: "Setări",
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
    edit: "Editează",
    cancel: "Anulează",
    save: "Salvează",
    descriptionLabel: "Descriere",
    stepsLabel: "Pași (unul pe linie)",
    tipsLabel: "Sfaturi (unul pe linie)",
    imagesLabel: "Imagini",
    removeImage: "Șterge imaginea",
    pasteImageHint: "Lipește o imagine, sau alege un fișier — poți adăuga mai multe.",
    processingStatus: {
      translating: "Se traduce…",
      recalculating_nutrition: "Se recalculează valorile nutriționale…",
    },
  },
  importManager: {
    heading: "Importă din URL",
    urlLabel: "URL rețetă",
    categoryLabel: "Categorie",
    categoryPlaceholder: "Alege o categorie",
    add: "Adaugă",
    approve: "Aprobă",
    delete: "Șterge",
    instagramHint:
      "Funcționează și linkurile către postări sau reels de Instagram — rețeta este citită din descriere și comentarii, iar o fotografie reprezentativă este preluată automat. Nimic diferit de făcut: lipește linkul și adaugă-l ca pe orice alt URL.",
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
    calorieNinjasApiKeyLabel: "Cheie API CalorieNinjas",
    calorieNinjasApiKeyHelp:
      "Folosită pentru a căuta valorile nutriționale ale ingredientelor. Cheie gratuită: calorieninjas.com/api.",
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
  nutrition: {
    heading: "Valori nutriționale",
    calories: "Calorii",
    protein: "Proteine",
    carbs: "Carbohidrați",
    sugars: "Zaharuri",
    fat: "Grăsimi",
    servesEstimate: "Porții: ~{count}",
    perServing: "Per porție",
    wholeRecipe: "Rețeta întreagă",
    estimateNote: "estimat din cantitățile de ingrediente",
  },
  ingredientRefresh: {
    heading: "Date nutriționale ingrediente",
    description:
      "Reface datele nutriționale CalorieNinjas pentru fiecare ingredient deja existent în baza de date — util după adăugarea unei chei API (ingredientele rezolvate înainte de asta au valori zero) sau dacă datele sursă s-au schimbat. Nu re-parsează lista de ingrediente a niciunei rețete; pentru asta folosește \"Calculează valori nutriționale\" pe o rețetă.",
    button: "Reparsează toate ingredientele",
    buttonBusy: "Se reparsează…",
    statuses: {
      never_run: "Nu a rulat încă.",
      queued: "În coadă…",
      processing: "Se reparsează ingredientele…",
      done: "Finalizat.",
      failed: "Eșuat.",
    },
    updatedCount: "{count} ingredient(e) actualizat(e)",
  },
};

export default ro;

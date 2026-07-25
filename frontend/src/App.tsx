import { Link, NavLink, Route, Routes } from "react-router-dom";
import { CategoryManager } from "./backoffice/CategoryManager";
import { ImportManager } from "./backoffice/ImportManager";
import { LoginForm } from "./backoffice/LoginForm";
import { RecipeManager } from "./backoffice/RecipeManager";
import { useAuth } from "./auth/AuthContext";
import { RecipeBrowser } from "./frontoffice/RecipeBrowser";
import { RecipeDetail } from "./frontoffice/RecipeDetail";
import { SUPPORTED_LANGUAGES } from "./i18n/config";
import { useLanguage } from "./i18n/LanguageContext";
import { secondaryButton } from "./ui/buttonStyles";

function navLinkClasses({ isActive }: { isActive: boolean }): string {
  return isActive ? "font-medium text-terracotta" : "text-ink/70 hover:text-ink";
}

function LanguageSwitcher() {
  const { language, setLanguage } = useLanguage();

  return (
    <div className="flex gap-1" role="group" aria-label="Language">
      {SUPPORTED_LANGUAGES.map((code) => (
        <button
          key={code}
          type="button"
          onClick={() => setLanguage(code)}
          aria-pressed={language === code}
          className={
            "rounded-md px-2 py-1 text-xs font-semibold uppercase transition-colors " +
            (language === code
              ? "bg-terracotta text-white"
              : "text-ink/60 hover:bg-olive-light")
          }
        >
          {code}
        </button>
      ))}
    </div>
  );
}

function BackofficePage() {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <LoginForm />;
  }

  return (
    <div className="space-y-10">
      <CategoryManager />
      <ImportManager />
      <RecipeManager />
    </div>
  );
}

export function App() {
  const { t } = useLanguage();
  const { isAuthenticated, logout } = useAuth();

  return (
    <div className="min-h-screen bg-cream text-ink">
      <header className="border-b border-olive-light bg-cream-card">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4 sm:px-6">
          <Link to="/" className="font-serif text-2xl font-semibold text-ink">
            {t.brand}
          </Link>
          <div className="flex items-center gap-4">
            <nav className="flex items-center gap-4 text-sm">
              <NavLink to="/" end className={navLinkClasses}>
                {t.nav.recipes}
              </NavLink>
              <NavLink to="/backoffice" className={navLinkClasses}>
                {t.nav.backoffice}
              </NavLink>
              {isAuthenticated && (
                <button type="button" onClick={logout} className={secondaryButton}>
                  {t.nav.logout}
                </button>
              )}
            </nav>
            <LanguageSwitcher />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-6 sm:px-6">
        <Routes>
          <Route path="/" element={<RecipeBrowser />} />
          <Route path="/recipes/:id" element={<RecipeDetail />} />
          <Route path="/backoffice" element={<BackofficePage />} />
        </Routes>
      </main>
    </div>
  );
}

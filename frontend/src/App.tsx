import { Link, Navigate, NavLink, Outlet, Route, Routes } from "react-router-dom";
import { AccountPage } from "./account/AccountPage";
import { RecipeSubmitForm } from "./account/RecipeSubmitForm";
import { CategoryManager } from "./backoffice/CategoryManager";
import { IngredientRefreshPanel } from "./backoffice/IngredientRefreshPanel";
import { ImportManager } from "./backoffice/ImportManager";
import { LoginForm } from "./backoffice/LoginForm";
import { RecipeManager } from "./backoffice/RecipeManager";
import { SettingsManager } from "./backoffice/SettingsManager";
import { SignupForm } from "./auth/SignupForm";
import { VerifyEmailPage } from "./auth/VerifyEmailPage";
import { useAuth } from "./auth/AuthContext";
import { LandingPage } from "./frontoffice/LandingPage";
import { RecipeBrowser } from "./frontoffice/RecipeBrowser";
import { RecipeDetail } from "./frontoffice/RecipeDetail";
import { SUPPORTED_LANGUAGES } from "./i18n/config";
import { useLanguage } from "./i18n/LanguageContext";
import { TermsPage } from "./legal/TermsPage";
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

function RecipesPage() {
  const { t } = useLanguage();
  return (
    <div className="space-y-10">
      <CategoryManager />
      <section
        aria-labelledby="recipes-heading"
        className="rounded-lg bg-cream-card p-5 ring-1 ring-black/5"
      >
        <h2 id="recipes-heading" className="font-serif text-2xl font-semibold text-ink">
          {t.recipeManager.heading}
        </h2>
        <ImportManager />
        <RecipeManager />
      </section>
    </div>
  );
}

function SettingsPage() {
  return (
    <div className="space-y-10">
      <SettingsManager />
      <IngredientRefreshPanel />
    </div>
  );
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function BackofficeLayout() {
  const { isAuthenticated, user } = useAuth();
  const { t } = useLanguage();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  if (!user?.is_admin) {
    return (
      <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
        {t.backoffice.accessDenied}
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <nav className="flex gap-4 border-b border-olive-light pb-3 text-sm" aria-label="Backoffice">
        <NavLink to="/backoffice" end className={navLinkClasses}>
          {t.nav.backofficeRecipes}
        </NavLink>
        {user.is_super_admin && (
          <NavLink to="/backoffice/settings" className={navLinkClasses}>
            {t.nav.backofficeSettings}
          </NavLink>
        )}
      </nav>
      <Outlet />
    </div>
  );
}

function RequireSuperAdmin({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const { t } = useLanguage();
  if (!user?.is_super_admin) {
    return (
      <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
        {t.backoffice.accessDenied}
      </p>
    );
  }
  return <>{children}</>;
}

function HomeRoute() {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <RecipeBrowser /> : <LandingPage />;
}

export function App() {
  const { t } = useLanguage();
  const { isAuthenticated, user, logout } = useAuth();

  return (
    <div className="flex min-h-screen flex-col bg-cream text-ink">
      <header className="border-b border-olive-light bg-cream-card">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4 sm:px-6">
          <Link to="/" className="font-serif text-2xl font-semibold text-ink">
            {t.brand}
          </Link>
          <div className="flex items-center gap-4">
            <nav className="flex items-center gap-4 text-sm">
              <NavLink to="/recipes" className={navLinkClasses}>
                {t.nav.recipes}
              </NavLink>
              {user?.is_admin && (
                <NavLink to="/backoffice" className={navLinkClasses}>
                  {t.nav.backoffice}
                </NavLink>
              )}
              {isAuthenticated ? (
                <>
                  <NavLink to="/account" className={navLinkClasses}>
                    {t.nav.account}
                  </NavLink>
                  <button type="button" onClick={logout} className={secondaryButton}>
                    {t.nav.logout}
                  </button>
                </>
              ) : (
                <>
                  <NavLink to="/login" className={navLinkClasses}>
                    {t.nav.login}
                  </NavLink>
                  <NavLink to="/signup" className={navLinkClasses}>
                    {t.nav.signup}
                  </NavLink>
                </>
              )}
            </nav>
            <LanguageSwitcher />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl flex-1 px-4 py-6 sm:px-6">
        <Routes>
          <Route path="/" element={<HomeRoute />} />
          <Route path="/recipes" element={<RecipeBrowser />} />
          <Route path="/recipes/:id" element={<RecipeDetail />} />
          <Route path="/login" element={isAuthenticated ? <Navigate to="/" replace /> : <LoginForm />} />
          <Route path="/signup" element={isAuthenticated ? <Navigate to="/" replace /> : <SignupForm />} />
          <Route path="/verify-email" element={<VerifyEmailPage />} />
          <Route path="/terms" element={<TermsPage />} />
          <Route
            path="/account"
            element={
              <RequireAuth>
                <AccountPage />
              </RequireAuth>
            }
          />
          <Route
            path="/submit-recipe"
            element={
              <RequireAuth>
                <RecipeSubmitForm />
              </RequireAuth>
            }
          />
          <Route path="/backoffice" element={<BackofficeLayout />}>
            <Route index element={<RecipesPage />} />
            <Route
              path="settings"
              element={
                <RequireSuperAdmin>
                  <SettingsPage />
                </RequireSuperAdmin>
              }
            />
          </Route>
        </Routes>
      </main>

      <footer className="border-t border-olive-light bg-cream-card py-4 text-center text-xs text-ink/50">
        <Link to="/terms" className="hover:text-ink hover:underline">
          {t.terms.navLink}
        </Link>
      </footer>
    </div>
  );
}

import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useLanguage } from "../i18n/LanguageContext";
import { primaryButton } from "../ui/buttonStyles";
import type { UserProfile } from "../types";

const inputClasses =
  "rounded-md border border-olive/30 bg-white px-3 py-2 text-sm text-ink focus:border-terracotta focus:outline-none";

// Profile + password only — recipe management (manual add, import, "my recipes") moved to its
// own page at /import, and favorites became a filter on the recipes page instead of a section
// here. See README Design Decisions, "Splitting Import out of the account page".
export function AccountPage() {
  const { t } = useLanguage();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSaved, setPasswordSaved] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);

  useEffect(() => {
    api.me().then(setProfile).catch((e) => setError(String(e)));
  }, []);

  const handleChangePassword = async (event: React.FormEvent) => {
    event.preventDefault();
    setPasswordError(null);
    setPasswordSaved(false);
    setChangingPassword(true);
    try {
      await api.changePassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setPasswordSaved(true);
    } catch (e) {
      setPasswordError(String(e));
    } finally {
      setChangingPassword(false);
    }
  };

  return (
    <div className="space-y-6">
      <section className="rounded-lg bg-cream-card p-5 ring-1 ring-black/5">
        <h2 className="font-serif text-2xl font-semibold text-ink">{t.account.heading}</h2>
        {error && (
          <p role="alert" className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}
        {profile && (
          <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
            <dt className="text-ink/60">{t.account.emailLabel}</dt>
            <dd className="text-ink">{profile.email}</dd>
          </dl>
        )}

        <h3 className="mt-5 font-serif text-lg font-semibold text-ink">
          {t.account.changePasswordHeading}
        </h3>
        <form onSubmit={handleChangePassword} className="mt-2 flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label htmlFor="account-current-password" className="text-sm font-medium text-ink/70">
              {t.account.currentPasswordLabel}
            </label>
            <input
              id="account-current-password"
              type="password"
              autoComplete="current-password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className={inputClasses}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="account-new-password" className="text-sm font-medium text-ink/70">
              {t.account.newPasswordLabel}
            </label>
            <input
              id="account-new-password"
              type="password"
              autoComplete="new-password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className={inputClasses}
            />
          </div>
          <button type="submit" disabled={changingPassword} className={primaryButton}>
            {t.account.changePasswordSubmit}
          </button>
        </form>
        {passwordError && (
          <p role="alert" className="mt-2 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {passwordError}
          </p>
        )}
        {passwordSaved && !passwordError && (
          <p role="status" className="mt-2 rounded-md bg-olive-light px-3 py-2 text-sm text-ink">
            {t.account.changePasswordSuccess}
          </p>
        )}
      </section>
    </div>
  );
}

import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { useLanguage } from "../i18n/LanguageContext";

type Status = "verifying" | "success" | "error";

export function VerifyEmailPage() {
  const { t } = useLanguage();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const [status, setStatus] = useState<Status>("verifying");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setError(t.verifyEmail.missingToken);
      return;
    }
    api
      .verifyEmail(token)
      .then(() => setStatus("success"))
      .catch((e) => {
        setStatus("error");
        setError(String(e));
      });
  }, [token]);

  return (
    <section className="mx-auto max-w-sm rounded-lg bg-cream-card p-6 ring-1 ring-black/5 text-center">
      {status === "verifying" && <p className="text-sm text-ink/70">{t.verifyEmail.verifying}</p>}

      {status === "success" && (
        <>
          <p role="status" className="rounded-md bg-olive-light px-3 py-2 text-sm text-ink">
            {t.verifyEmail.success}
          </p>
          <Link to="/login" className="mt-4 inline-block text-sm text-terracotta hover:underline">
            {t.verifyEmail.loginLink}
          </Link>
        </>
      )}

      {status === "error" && (
        <>
          <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
          <Link to="/login" className="mt-4 inline-block text-sm text-terracotta hover:underline">
            {t.verifyEmail.loginLink}
          </Link>
        </>
      )}
    </section>
  );
}

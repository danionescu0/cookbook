import { useEffect, useRef } from "react";

declare global {
  interface Window {
    turnstile?: {
      render: (
        container: HTMLElement,
        options: { sitekey: string; callback: (token: string) => void }
      ) => string;
      remove: (widgetId: string) => void;
    };
  }
}

interface TurnstileWidgetProps {
  siteKey: string;
  onToken: (token: string) => void;
}

export function TurnstileWidget({ siteKey, onToken }: TurnstileWidgetProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const widgetIdRef = useRef<string | null>(null);
  // A ref (not a `callback` effect dependency) so a new inline `onToken` on every parent render
  // doesn't tear down and re-render the widget — only `siteKey` changing should do that.
  const onTokenRef = useRef(onToken);
  useEffect(() => {
    onTokenRef.current = onToken;
  }, [onToken]);

  useEffect(() => {
    if (!siteKey || !containerRef.current) return;

    let cancelled = false;
    const renderWidget = () => {
      if (cancelled || !window.turnstile || !containerRef.current) return;
      widgetIdRef.current = window.turnstile.render(containerRef.current, {
        sitekey: siteKey,
        callback: (token) => onTokenRef.current(token),
      });
    };

    if (window.turnstile) {
      renderWidget();
      return () => {
        cancelled = true;
        if (widgetIdRef.current) window.turnstile?.remove(widgetIdRef.current);
      };
    }

    // The script tag in index.html is `async defer` — it may not be loaded yet when this
    // component first mounts, so poll briefly rather than assuming it's ready.
    const interval = setInterval(() => {
      if (window.turnstile) {
        clearInterval(interval);
        renderWidget();
      }
    }, 100);
    return () => {
      cancelled = true;
      clearInterval(interval);
      if (widgetIdRef.current) window.turnstile?.remove(widgetIdRef.current);
    };
  }, [siteKey]);

  return <div ref={containerRef} />;
}

import { useState } from "react";
import { BASE_URL } from "../api/client";
import { useLanguage } from "../i18n/LanguageContext";

interface ImageSliderProps {
  images: string[];
  alt: string;
}

// Manual only (no autoplay/timers) — a recipe photo set is small and the reader is here to
// read, not watch a show. Controls only render once there's something to switch between.
export function ImageSlider({ images, alt }: ImageSliderProps) {
  const { t } = useLanguage();
  const [index, setIndex] = useState(0);

  if (images.length === 0) return null;

  const hasMultiple = images.length > 1;
  const goToPrevious = () => setIndex((current) => (current - 1 + images.length) % images.length);
  const goToNext = () => setIndex((current) => (current + 1) % images.length);

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "ArrowLeft") goToPrevious();
    if (event.key === "ArrowRight") goToNext();
  };

  return (
    <div
      className="relative mt-4 aspect-video w-full overflow-hidden rounded-lg bg-olive-light"
      tabIndex={hasMultiple ? 0 : undefined}
      role={hasMultiple ? "group" : undefined}
      aria-roledescription={hasMultiple ? "carousel" : undefined}
      onKeyDown={hasMultiple ? handleKeyDown : undefined}
    >
      <img
        src={`${BASE_URL}${images[index]}`}
        alt={alt}
        className="h-full w-full object-cover"
      />

      {hasMultiple && (
        <>
          <button
            type="button"
            onClick={goToPrevious}
            aria-label={t.detail.previousPhoto}
            className="absolute left-3 top-1/2 flex h-12 w-12 -translate-y-1/2 items-center justify-center rounded-full bg-terracotta text-white shadow-lg ring-2 ring-white/80 transition-all hover:scale-110 hover:bg-terracotta-dark focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="3"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-6 w-6"
              aria-hidden="true"
            >
              <path d="M15 18l-6-6 6-6" />
            </svg>
          </button>
          <button
            type="button"
            onClick={goToNext}
            aria-label={t.detail.nextPhoto}
            className="absolute right-3 top-1/2 flex h-12 w-12 -translate-y-1/2 items-center justify-center rounded-full bg-terracotta text-white shadow-lg ring-2 ring-white/80 transition-all hover:scale-110 hover:bg-terracotta-dark focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="3"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-6 w-6"
              aria-hidden="true"
            >
              <path d="M9 18l6-6-6-6" />
            </svg>
          </button>
          <span className="absolute bottom-3 right-3 rounded-full bg-ink/70 px-2.5 py-1 text-xs font-semibold text-white">
            {t.detail.photoCount
              .replace("{current}", String(index + 1))
              .replace("{total}", String(images.length))}
          </span>
        </>
      )}
    </div>
  );
}

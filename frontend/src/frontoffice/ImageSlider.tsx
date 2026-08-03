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
            className="absolute left-2 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full bg-cream-card/90 text-xl text-ink shadow-sm transition-colors hover:bg-cream-card focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-terracotta"
          >
            <span aria-hidden="true">‹</span>
          </button>
          <button
            type="button"
            onClick={goToNext}
            aria-label={t.detail.nextPhoto}
            className="absolute right-2 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full bg-cream-card/90 text-xl text-ink shadow-sm transition-colors hover:bg-cream-card focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-terracotta"
          >
            <span aria-hidden="true">›</span>
          </button>
          <span className="absolute bottom-2 right-2 rounded-full bg-ink/60 px-2 py-0.5 text-xs font-medium text-white">
            {t.detail.photoCount
              .replace("{current}", String(index + 1))
              .replace("{total}", String(images.length))}
          </span>
        </>
      )}
    </div>
  );
}

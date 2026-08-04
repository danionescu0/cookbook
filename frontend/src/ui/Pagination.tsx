import { secondaryButton } from "./buttonStyles";

// Classic numbered pagination, windowed around the current page (first, last, current ± 1) with
// an ellipsis for any gap — full range once there's little enough to show it without crowding.
export function pageNumbersToShow(current: number, total: number): (number | "ellipsis")[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const candidates = [1, total, current - 1, current, current + 1].filter(
    (p) => p >= 1 && p <= total
  );
  const sorted = [...new Set(candidates)].sort((a, b) => a - b);
  const result: (number | "ellipsis")[] = [];
  let previous = 0;
  for (const page of sorted) {
    if (previous && page - previous > 1) result.push("ellipsis");
    result.push(page);
    previous = page;
  }
  return result;
}

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  ariaLabel: string;
  previousLabel: string;
  nextLabel: string;
}

export function Pagination({
  currentPage,
  totalPages,
  onPageChange,
  ariaLabel,
  previousLabel,
  nextLabel,
}: PaginationProps) {
  if (totalPages <= 1) return null;

  return (
    <nav aria-label={ariaLabel} className="mt-6 flex flex-wrap items-center justify-center gap-1">
      <button
        type="button"
        onClick={() => onPageChange(Math.max(1, currentPage - 1))}
        disabled={currentPage === 1}
        className={secondaryButton}
      >
        {previousLabel}
      </button>
      {pageNumbersToShow(currentPage, totalPages).map((entry, index) =>
        entry === "ellipsis" ? (
          <span key={`ellipsis-${index}`} className="px-2 text-ink/40" aria-hidden="true">
            …
          </span>
        ) : (
          <button
            key={entry}
            type="button"
            onClick={() => onPageChange(entry)}
            aria-current={entry === currentPage ? "page" : undefined}
            className={
              "flex h-9 w-9 items-center justify-center rounded-md text-sm font-medium transition-colors " +
              (entry === currentPage ? "bg-terracotta text-white" : "text-ink/70 hover:bg-olive-light")
            }
          >
            {entry}
          </button>
        )
      )}
      <button
        type="button"
        onClick={() => onPageChange(Math.min(totalPages, currentPage + 1))}
        disabled={currentPage === totalPages}
        className={secondaryButton}
      >
        {nextLabel}
      </button>
    </nav>
  );
}

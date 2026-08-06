interface IconProps {
  className?: string;
}

// Hand-rolled, no icon library — matches this project's "no external dependency for a handful
// of static assets" pattern (see src/i18n/). Built from simple primitives (circle/ellipse/rect)
// rather than hand-tuned bezier paths, so they render reliably without visual iteration.

export function FlameIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path d="M12 2c0 0-6 8-6 13a6 6 0 0 0 12 0c0-5-6-13-6-13z" fill="currentColor" opacity="0.35" />
      <path d="M12 8c0 0-3 4.5-3 7.5a3 3 0 0 0 6 0C15 12.5 12 8 12 8z" fill="currentColor" />
    </svg>
  );
}

export function DrumstickIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <ellipse cx="9" cy="9" rx="6" ry="5" fill="currentColor" transform="rotate(-35 9 9)" />
      <rect x="13" y="13" width="7" height="3" rx="1.5" fill="currentColor" transform="rotate(-35 13 13)" />
      <circle cx="19.2" cy="17.8" r="2.2" fill="currentColor" />
    </svg>
  );
}

export function WheatIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <line x1="12" y1="21" x2="12" y2="5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <ellipse cx="9.5" cy="7" rx="2.3" ry="1.3" fill="currentColor" transform="rotate(-30 9.5 7)" />
      <ellipse cx="14.5" cy="7" rx="2.3" ry="1.3" fill="currentColor" transform="rotate(30 14.5 7)" />
      <ellipse cx="9.5" cy="10.5" rx="2.3" ry="1.3" fill="currentColor" transform="rotate(-30 9.5 10.5)" />
      <ellipse cx="14.5" cy="10.5" rx="2.3" ry="1.3" fill="currentColor" transform="rotate(30 14.5 10.5)" />
      <ellipse cx="9.5" cy="14" rx="2.3" ry="1.3" fill="currentColor" transform="rotate(-30 9.5 14)" />
      <ellipse cx="14.5" cy="14" rx="2.3" ry="1.3" fill="currentColor" transform="rotate(30 14.5 14)" />
    </svg>
  );
}

export function SugarCubesIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <rect x="4" y="4" width="7" height="7" rx="1" fill="currentColor" opacity="0.9" />
      <rect x="13" y="4" width="7" height="7" rx="1" fill="currentColor" opacity="0.7" />
      <rect x="4" y="13" width="7" height="7" rx="1" fill="currentColor" opacity="0.7" />
      <rect x="13" y="13" width="7" height="7" rx="1" fill="currentColor" opacity="0.5" />
    </svg>
  );
}

export function DropletIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path d="M12 2c0 0-6 8-6 13a6 6 0 0 0 12 0c0-5-6-13-6-13z" fill="currentColor" />
    </svg>
  );
}

export function ScaleIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <line x1="12" y1="4" x2="12" y2="18" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="4" y1="7" x2="20" y2="7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M4 7l-2.5 5a2.5 2.5 0 0 0 5 0z" fill="currentColor" opacity="0.7" />
      <path d="M20 7l-2.5 5a2.5 2.5 0 0 0 5 0z" fill="currentColor" opacity="0.7" />
      <rect x="8" y="18" width="8" height="2.2" rx="1.1" fill="currentColor" />
    </svg>
  );
}

export function ServingsIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <circle cx="9" cy="8" r="3" fill="currentColor" />
      <path
        d="M3 20c0-3.5 2.7-6 6-6s6 2.5 6 6"
        stroke="currentColor"
        strokeWidth="1.5"
        fill="none"
        strokeLinecap="round"
      />
      <circle cx="17" cy="7" r="2.4" fill="currentColor" opacity="0.6" />
      <path
        d="M13 20c.3-2.8 2-5 4.3-5.4"
        stroke="currentColor"
        strokeWidth="1.5"
        fill="none"
        strokeLinecap="round"
        opacity="0.6"
      />
    </svg>
  );
}

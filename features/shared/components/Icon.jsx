/**
 * The icon set, drawn once.
 *
 * Inline SVG rather than an icon font or a package: these paint with the first
 * frame, need no network request, and inherit `currentColor` so a lime button
 * and a dim label use the same glyph without a second asset. On the network
 * this app is built for, an icon font that arrives late is a screen that looks
 * broken for two seconds.
 *
 * Outlined, 1.6 stroke, 24-unit box, matching the reference screens.
 */

const PATHS = {
  back: <path d="M15 18 9 12l6-6" />,
  pin: (
    <>
      <path d="M12 21s7-6.2 7-11a7 7 0 1 0-14 0c0 4.8 7 11 7 11Z" />
      <circle cx="12" cy="10" r="2.6" />
    </>
  ),
  home: <path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-9.5Z" />,
  work: (
    <>
      <rect x="3" y="7" width="18" height="13" rx="2" />
      <path d="M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
    </>
  ),
  airport: <path d="M2 13.5 21 4l-4.5 9.5L21 20 2 13.5Z" />,
  search: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3.5 2" />
    </>
  ),
  star: <path d="m12 3 2.7 5.8 6.3.8-4.6 4.4 1.2 6.3-5.6-3.1-5.6 3.1 1.2-6.3L3 9.6l6.3-.8L12 3Z" />,
  check: <path d="m5 13 4.5 4.5L19 7" />,
  phone: (
    <path d="M6.5 3h3l1.5 4-2 1.5a12 12 0 0 0 5.5 5.5L16 12l4 1.5v3a2 2 0 0 1-2.2 2A16.5 16.5 0 0 1 3.5 5.2 2 2 0 0 1 5.5 3h1Z" />
  ),
  message: <path d="M4 5h16v11H8l-4 4V5Z" />,
  shield: <path d="M12 3 5 6v6c0 4.2 3 7.8 7 9 4-1.2 7-4.8 7-9V6l-7-3Z" />,
  route: (
    <>
      <circle cx="6" cy="6" r="2.4" />
      <circle cx="18" cy="18" r="2.4" />
      <path d="M6 8.4V13a3 3 0 0 0 3 3h6.6" />
    </>
  ),
  seat: (
    <>
      <path d="M7 4h4a3 3 0 0 1 3 3v7H7V4Z" />
      <path d="M7 14h10a2 2 0 0 1 2 2v4H7" />
    </>
  ),
  volume: (
    <>
      <path d="M11 5 6 9H3v6h3l5 4V5Z" />
      <path d="M15.5 9a4 4 0 0 1 0 6" />
    </>
  ),
  wallet: (
    <>
      <rect x="3" y="6" width="18" height="13" rx="2" />
      <path d="M16 12.5h2" />
    </>
  ),
  user: (
    <>
      <circle cx="12" cy="8" r="3.6" />
      <path d="M5 20a7 7 0 0 1 14 0" />
    </>
  ),
  arrow: <path d="M5 12h13m0 0-5-5m5 5-5 5" />,
};

export default function Icon({ name, size = 20, filled = false, ...rest }) {
  const path = PATHS[name];
  if (!path) return null;

  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill={filled ? 'currentColor' : 'none'}
      stroke={filled ? 'none' : 'currentColor'}
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {path}
    </svg>
  );
}

/** The V mark: two roads meeting at a pickup point. */
export function VoraMark({ size = 30 }) {
  return (
    <svg viewBox="0 0 64 64" width={size} height={size} aria-hidden="true">
      <path
        d="M12 12 L32 52 L52 12"
        fill="none"
        stroke="var(--accent)"
        strokeWidth="7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="32" cy="52" r="6" fill="var(--accent)" />
    </svg>
  );
}

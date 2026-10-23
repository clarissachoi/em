// Small stroke icons used across the app.

const PATHS: Record<string, string> = {
  mic: 'M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3Z M5 11a7 7 0 0 0 14 0 M12 18v3',
  arrow: 'M5 12h14 M13 6l6 6-6 6',
  run: 'M13 4a1.5 1.5 0 1 0 3 0 1.5 1.5 0 0 0-3 0 M7 21l3-6 3 2v5 M10 15l1-5 4 2 3-1 M8 10l3-1',
  food: 'M7 3v8a2 2 0 0 0 4 0V3 M9 11v10 M17 21V3c-2 1-3 4-3 7h3',
  calendar: 'M4 6h16v14H4z M4 10h16 M8 3v4 M16 3v4',
  doc: 'M7 3h7l4 4v14H7z M14 3v4h4 M10 12h5 M10 16h5',
  lab: 'M9 3h6 M10 3v6l-5 9a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-9V3',
  chat: 'M4 5h16v11H9l-5 4z',
  globe: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z M3 12h18 M12 3c3 3 3 15 0 18 M12 3c-3 3-3 15 0 18',
  check: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z M8 12l3 3 5-6',
  sun: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z M12 2v2 M12 20v2 M4 12H2 M22 12h-2 M5 5l1.5 1.5 M17.5 17.5 19 19 M5 19l1.5-1.5 M17.5 6.5 19 5',
  close: 'M6 6l12 12 M18 6 6 18',
  user: 'M12 4a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z M4 21c1-4 4-6 8-6s7 2 8 6',
  clock: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z M12 7v5l3 2',
  pin: 'M12 21s-6-5.5-6-11a6 6 0 0 1 12 0c0 5.5-6 11-6 11Z M12 8a2 2 0 1 0 0 4 2 2 0 0 0 0-4Z',
  bolt: 'M13 3 5 14h6l-1 7 8-11h-6z',
  plus: 'M12 5v14 M5 12h14',
  sparkle: 'M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z M19 16l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z',
  clipboard: 'M9 4h6v3H9z M7 5H5v16h14V5h-2 M8 12h8 M8 16h5',
  ear: 'M7 9a5 5 0 0 1 10 0c0 3-3 4-3 7a3 3 0 0 1-6 0 M10 9a2 2 0 0 1 4 0',
  stop: 'M7 7h10v10H7z',
  wave: 'M4 10v4 M8 7v10 M12 4v16 M16 7v10 M20 10v4',
  shield: 'M12 3l8 3v6c0 4.5-3.4 8.3-8 9-4.6-.7-8-4.5-8-9V6z M8.5 12l2.5 2.5 4.5-5',
  eye: 'M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z',
  tooth: 'M7 3c-2 0-3.5 1.7-3.5 4 0 3 1.5 5 2 8s1 6 2.5 6 1.7-3 2.5-5c.4-1 .8-1 1 0 .8 2 1 5 2.5 5s2-3 2.5-6 2-5 2-8c0-2.3-1.5-4-3.5-4-1.7 0-2.8 1-4 1S8.7 3 7 3Z',
  baby: 'M12 4a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z M6 21v-4a6 6 0 0 1 12 0v4',
  heart: 'M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10Z',
  gift: 'M4 11h16v10H4z M3 7h18v4H3z M12 7v14 M12 7c-2 0-4-1-4-2.5S10 3 12 7c2-4 4-2.5 4-1S14 7 12 7Z',
}

/** Inline SVG icon by name. Decorative unless a label is given. */
export default function Icon({ name, size = 16, label }: { name: keyof typeof PATHS | string; size?: number; label?: string }) {
  return (
    <svg
      width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" role={label ? 'img' : undefined} aria-label={label} aria-hidden={label ? undefined : true}
    >
      <path d={PATHS[name] ?? ''} />
    </svg>
  )
}

/** Mood face: 0 low, 1 okay, 2 good, 3 great. */
export function MoodFace({ level, size = 18 }: { level: number; size?: number }) {
  const mouth = ['M8 16c2-2 6-2 8 0', 'M8.5 15.5h7', 'M8 14.5c2 1.5 6 1.5 8 0', 'M7.5 13.5c2 3 7 3 9 0']
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden>
      <circle cx="12" cy="12" r="9" />
      <path d="M9 9.5h.01 M15 9.5h.01" strokeWidth="2.4" />
      <path d={mouth[level]} />
    </svg>
  )
}

import type { CSSProperties } from "react";

const paths = {
  compass: "m16.5 7.5-3 6-6 3 3-6 6-3Z M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Z",
  grid: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  calendar: "M8 2v4 M16 2v4 M3 10h18 M5 4h14a2 2 0 0 1 2 2v14H3V6a2 2 0 0 1 2-2Z M7 14h3 M14 14h3 M7 18h3",
  wallet: "M20 8V5H4a2 2 0 0 1 0-4h14v4 M4 5a2 2 0 0 0-2 2v13h20V8H4 M22 12h-6v5h6 M18 14.5h.01",
  people: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z M17 3a4 4 0 0 1 0 8 M22 21v-2a4 4 0 0 0-3-3.87",
  arrow: "M4 12h16 M14 6l6 6-6 6",
  pin: "M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0Z M12 7a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z",
  receipt: "M5 3l3 2 4-2 4 2 3-2v18l-3-2-4 2-4-2-3 2V3Z M9 9h6 M9 13h6",
  lock: "M6 10h12v11H6V10Z M8 10V6a4 4 0 0 1 8 0v4 M12 14v3",
  spark: "m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z",
  check: "m5 12 4 4L19 6",
  home: "m3 10 9-7 9 7 M5 9v12h14V9 M9 21v-8h6v8",
  food: "M4 3v6a3 3 0 0 0 6 0V3 M7 3v19 M18 3c-3 3-4 6-3 9h4 M19 3v19",
  car: "m5 4-3 8v6h20v-6l-3-8H5Z M3 11h18 M6 15h.01 M18 15h.01 M5 18v3 M19 18v3",
  leaf: "M20 3C9 2 2 9 5 16s17 2 15-13Z M4 21 16 9",
} as const;

export type IconName = keyof typeof paths;
export function Icon({ name, size = 18, style }: { name: IconName; size?: number; style?: CSSProperties }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={style}><path d={paths[name]} /></svg>;
}

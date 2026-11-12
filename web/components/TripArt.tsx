import type { Theme } from "@/lib/types";

// The banner art at the top of a trip page: flat shapes in the theme's colours, no photos.
// Sunset: a striped sun over a wave. Night Swim: a moon over waves. Campfire: mountains and stars.
export function TripArt({ theme = "sunset" }: { theme?: Theme }) {
  return (
    <svg viewBox="0 0 390 196" preserveAspectRatio="xMidYMax slice" className="block h-[196px] w-full" aria-hidden="true">
      {theme === "night_swim" ? <NightSwim /> : theme === "campfire" ? <Campfire /> : <Sunset />}
    </svg>
  );
}

function Sunset() {
  return (
    <>
      <circle cx="268" cy="150" r="104" fill="var(--pop)" />
      <rect x="150" y="112" width="260" height="9" fill="var(--ground)" />
      <rect x="150" y="132" width="260" height="12" fill="var(--ground)" />
      <rect x="150" y="156" width="260" height="15" fill="var(--ground)" />
      <path d="M0 176 C 40 160, 80 192, 120 176 S 200 160, 240 176 S 320 192, 390 172 L 390 196 L 0 196 Z" fill="var(--hot)" />
      <circle cx="54" cy="58" r="5" fill="var(--ink)" />
      <circle cx="96" cy="30" r="3" fill="var(--ink)" />
      <circle cx="20" cy="110" r="3" fill="var(--ink)" />
    </>
  );
}

function NightSwim() {
  const wave = (y: number) => `M0 ${y} C 30 ${y - 12}, 60 ${y + 12}, 90 ${y} S 150 ${y - 12}, 180 ${y} S 240 ${y + 12}, 270 ${y} S 330 ${y - 12}, 390 ${y}`;
  return (
    <>
      <circle cx="292" cy="72" r="46" fill="var(--ink)" />
      <circle cx="312" cy="58" r="40" fill="var(--ground)" />
      <path d={wave(128)} stroke="var(--pop)" strokeWidth="6" fill="none" />
      <path d={wave(152)} stroke="var(--hot)" strokeWidth="6" fill="none" />
      <path d={wave(176)} stroke="var(--pop)" strokeWidth="6" fill="none" />
      <circle cx="70" cy="40" r="3" fill="var(--ink)" />
      <circle cx="160" cy="24" r="2" fill="var(--ink)" />
      <circle cx="210" cy="64" r="3" fill="var(--ink)" />
    </>
  );
}

function Campfire() {
  return (
    <>
      <path d="M120 196 L 230 70 L 340 196 Z" fill="var(--hot)" />
      <path d="M230 70 L 252 96 L 238 92 L 230 104 L 220 92 L 208 96 Z" fill="var(--ground)" />
      <path d="M220 196 L 320 96 L 420 196 Z" fill="var(--pop)" />
      <path d="M0 196 L 70 130 L 150 196 Z" fill="var(--outline)" />
      <circle cx="60" cy="44" r="3" fill="var(--ink)" />
      <circle cx="120" cy="22" r="2" fill="var(--ink)" />
      <circle cx="350" cy="36" r="3" fill="var(--ink)" />
      <circle cx="170" cy="58" r="2" fill="var(--ink)" />
    </>
  );
}

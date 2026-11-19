// Initials in coloured circles: who's going, who you pay, who did what. A person's colour comes
// from their position on the trip, so it's the same everywhere on the page. The first person
// gets the theme's accent; the rest a fixed set. Every pair passes 4.5:1.
const COLORS: [string, string][] = [
  ["var(--accent)", "var(--accent-ink)"],
  ["#f4797e", "#2a0a0e"],
  ["#7cc0ea", "#071a2a"],
  ["#ffd08a", "#2a1a06"],
  ["#c7b6f2", "#1a1030"],
  ["#9be6aa", "#06240e"],
  ["#ffb3c7", "#2a0614"],
];

export function avatarColor(index: number): { background: string; color: string } {
  const [background, color] = COLORS[index % COLORS.length];
  return { background, color };
}

/** One person's initial. `index`: their position on the trip. */
export function Avatar({ name, index, size = 42 }: { name: string; index: number; size?: number }) {
  return (
    <span
      aria-hidden="true"
      className="avatar"
      style={{ ...avatarColor(index), width: size, height: size, fontSize: Math.round(size * 0.4) }}
    >
      {name.trim()[0]?.toUpperCase() ?? "?"}
    </span>
  );
}

/** Overlapping initials. `colorIndexes`: each person's position on the trip. */
export function Avatars({ names, colorIndexes, max = 6, size = 30 }: { names: string[]; colorIndexes?: number[]; max?: number; size?: number }) {
  const shown = names.slice(0, max);
  const more = names.length - shown.length;
  const ring = "border-2 border-[#1a2338]";
  return (
    <span className="flex flex-none" aria-hidden="true">
      {shown.map((name, i) => (
        <span
          key={`${name}-${i}`}
          style={{ ...avatarColor(colorIndexes?.[i] ?? i), width: size, height: size, fontSize: Math.round(size * 0.4) }}
          className={`avatar ${ring} ${i ? "-ml-2" : ""}`}
        >
          {name.trim()[0]?.toUpperCase() ?? "?"}
        </span>
      ))}
      {more > 0 && (
        <span style={{ width: size, height: size }} className={`avatar -ml-2 ${ring} bg-fill text-xs text-ink`}>
          +{more}
        </span>
      )}
    </span>
  );
}

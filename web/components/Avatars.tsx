// Initials in coloured circles, overlapping: who's going. The colours are fixed per position so a
// person keeps theirs as long as the member list doesn't change order. All pass 4.5:1 with dark text.
const COLORS = ["#ffc94a", "#ff6b4a", "#7fd3ff", "#c9a2ff", "#8ef0b0", "#ffb3c7"];

export function avatarColor(index: number): string {
  return COLORS[index % COLORS.length];
}

export function Avatars({ names, max = 6 }: { names: string[]; max?: number }) {
  const shown = names.slice(0, max);
  const more = names.length - shown.length;
  return (
    <div className="flex" aria-hidden="true">
      {shown.map((name, i) => (
        <span
          key={`${name}-${i}`}
          style={{ background: avatarColor(i) }}
          className={`inline-flex size-9 items-center justify-center rounded-full border-2 border-ground text-sm font-bold text-ground ${i ? "-ml-2.5" : ""}`}
        >
          {name.trim()[0]?.toUpperCase() ?? "?"}
        </span>
      ))}
      {more > 0 && (
        <span className="-ml-2.5 inline-flex size-9 items-center justify-center rounded-full border-2 border-ground bg-surface text-xs font-bold text-ink">
          +{more}
        </span>
      )}
    </div>
  );
}

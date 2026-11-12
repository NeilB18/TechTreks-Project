// The banner art at the top of a trip page: flat shapes, no photos. Sunset only for now
// (a striped sun over a wave); Night Swim and Campfire come with the theme picker.
export function TripArt() {
  return (
    <svg viewBox="0 0 390 196" preserveAspectRatio="xMidYMax slice" className="block h-[196px] w-full" aria-hidden="true">
      <circle cx="268" cy="150" r="104" fill="var(--pop)" />
      <rect x="150" y="112" width="260" height="9" fill="var(--ground)" />
      <rect x="150" y="132" width="260" height="12" fill="var(--ground)" />
      <rect x="150" y="156" width="260" height="15" fill="var(--ground)" />
      <path d="M0 176 C 40 160, 80 192, 120 176 S 200 160, 240 176 S 320 192, 390 172 L 390 196 L 0 196 Z" fill="var(--hot)" />
      <circle cx="54" cy="58" r="5" fill="var(--ink)" />
      <circle cx="96" cy="30" r="3" fill="var(--ink)" />
      <circle cx="20" cy="110" r="3" fill="var(--ink)" />
    </svg>
  );
}

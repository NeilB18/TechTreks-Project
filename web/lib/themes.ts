import type { Theme } from "./types";

// The trip page's looks (colours in app/globals.css, art in components/TripArt.tsx). Plain data,
// so both the server page and the picker in the browser can use it.
export const THEMES: { id: Theme; name: string; note: string }[] = [
  { id: "sunset", name: "Sunset", note: "Beach & coast" },
  { id: "night_swim", name: "Night Swim", note: "City" },
  { id: "campfire", name: "Campfire", note: "Outdoors" },
];

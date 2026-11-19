import type { Theme } from "./types";

// The trip themes: one of our own photos each (web/public/themes, free under the Unsplash License,
// credited in web/README.md) and an accent colour (app/globals.css). The bot picks one from the
// destination; people on the trip can switch. Plain data, so the server page and the picker in the
// browser can both use it.
export type ThemeInfo = {
  id: Theme;
  name: string;
  note: string; // what it's for, shown in the picker
  photo: string;
  alt: string;
  // The bot can only save the themes its backend knows. Snow and Desert road arrive with the
  // bot-themes PR; until then a trip can show them but the picker doesn't offer them.
  pickable: boolean;
};

export const THEMES: ThemeInfo[] = [
  { id: "sunset", name: "Beach", note: "Beaches, coasts, spring break", photo: "/themes/sunset.jpg",
    alt: "Palm trees at sunset, reflected in still water", pickable: true },
  { id: "night_swim", name: "City nights", note: "Any city", photo: "/themes/night_swim.jpg",
    alt: "A downtown street at night with red traffic lights", pickable: true },
  { id: "campfire", name: "Mountains", note: "Cabins, hiking, national parks", photo: "/themes/campfire.jpg",
    alt: "Blue ridges of the Smoky Mountains at dusk", pickable: true },
  { id: "snow", name: "Snow", note: "Ski trips, winter break", photo: "/themes/snow.jpg",
    alt: "Pine trees in front of snowy mountain peaks", pickable: false },
  { id: "desert", name: "Desert road", note: "Road trips, Vegas, the Southwest", photo: "/themes/desert.jpg",
    alt: "A long empty road across a desert valley", pickable: false },
];

export const DEFAULT_THEME: Theme = "sunset";

/** The theme's info; unknown or missing ids get the default (a new trip with no destination yet). */
export function themeInfo(id: string | null | undefined): ThemeInfo {
  return THEMES.find((t) => t.id === id) ?? THEMES[0];
}

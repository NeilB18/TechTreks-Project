import type { Metadata } from "next";
import { Mona_Sans } from "next/font/google";

import { SITE_NAME } from "@/lib/site";
import "./globals.css";

// Self-hosted by next/font: no requests to Google from the visitor's browser. The width axis
// (wdth) is what makes titles wide (font-stretch: 125%).
const mona = Mona_Sans({ variable: "--font-mona", subsets: ["latin"], axes: ["wdth"] });

export const metadata: Metadata = {
  title: { default: SITE_NAME, template: `%s | ${SITE_NAME}` },
  description: "Plan the trip in the group chat: @tripbot keeps the plan, splits what everyone spends, and keeps budgets honest.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${mona.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <a href="#main" className="sr-only z-50 rounded-xl bg-white px-4 py-2 font-bold text-ground focus:not-sr-only focus:fixed focus:top-3 focus:left-3">
          Skip to content
        </a>
        {children}
      </body>
    </html>
  );
}

import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TechTreks · Your next adventure",
  description: "Your group trip's plans, expenses and how to settle up.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className="h-full antialiased"
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}

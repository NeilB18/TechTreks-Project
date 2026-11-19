import Image from "next/image";
import type { ReactNode } from "react";

import type { ThemeInfo } from "@/lib/themes";

// A trip's theme photo, two ways (design canvas: Final designs, "Trip tab").
//
// PhotoBackdrop: the same photo blurred far out of focus, behind the top of the page, fading
// into the dark background. It only gives the page the photo's colours, so a small copy is enough.
//
// PhotoHeader: the photo across the top (about 300px on a phone), softly blurred and darkened
// so the title on it stays readable, fading out at the bottom. Children sit on top of it.

export function PhotoBackdrop({ theme, height = 1300 }: { theme: ThemeInfo; height?: number }) {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 top-0 overflow-hidden" style={{ height }}>
      <Image
        src={theme.photo}
        alt=""
        fill
        sizes="160px"
        loading="eager"
        className="scale-125 object-cover"
        style={{ filter: "blur(40px) saturate(1.35) brightness(0.7)" }}
      />
      <div className="absolute inset-0 bg-[linear-gradient(180deg,rgb(15_22_40/0.3)_0%,rgb(15_22_40/0.6)_45%,var(--ground)_100%)]" />
    </div>
  );
}

export function PhotoHeader({
  theme,
  className = "h-[300px]",
  blur = 12,
  children,
}: {
  theme: ThemeInfo;
  className?: string;
  blur?: number; // px; the trip page uses 12, the landing page 8
  children: ReactNode;
}) {
  return (
    <div className={`relative overflow-hidden ${className}`}>
      {/* Bigger than the box, so the blur doesn't leave soft edges at the sides. */}
      <div className="absolute -inset-6 [mask-image:linear-gradient(180deg,#000_72%,transparent_100%)]">
        <Image
          src={theme.photo}
          alt={theme.alt}
          fill
          loading="eager"
          fetchPriority="high"
          sizes="(max-width: 672px) 100vw, 672px"
          className="object-cover object-[center_45%]"
          style={{ filter: `blur(${blur}px) saturate(1.15) brightness(0.92)` }}
        />
      </div>
      <div
        aria-hidden="true"
        className="absolute inset-0 bg-[linear-gradient(180deg,rgb(10_14_26/0.5)_0%,rgb(10_14_26/0.42)_32%,rgb(10_14_26/0.42)_72%,rgb(15_22_40/0)_100%)]"
      />
      {children}
    </div>
  );
}

import type { ReactNode } from "react";

// Line icons used across the site: 24px grid, 1.8px stroke, round ends. Decorative only
// (aria-hidden); whatever they sit next to carries the meaning.

type Props = { size?: number; className?: string; stroke?: number };

function Svg({ size = 22, className, stroke = 1.8, children }: Props & { children: ReactNode }) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={stroke}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      {children}
    </svg>
  );
}

export const CalendarIcon = (p: Props) => (
  <Svg {...p}><rect x="3.5" y="5" width="17" height="15.5" rx="2.5" /><path d="M3.5 10h17M8 3v4M16 3v4" /></Svg>
);
export const PinIcon = (p: Props) => (
  <Svg {...p}><path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z" /><circle cx="12" cy="9.5" r="2.5" /></Svg>
);
export const HomeIcon = (p: Props) => (
  <Svg {...p}><path d="M3 10.5L12 4l9 6.5V20H3z" /><path d="M9.5 20v-5.5h5V20" /></Svg>
);
export const PeopleIcon = (p: Props) => (
  <Svg {...p}>
    <circle cx="9" cy="8" r="3.5" /><path d="M2.5 20c0-3.6 2.9-6.5 6.5-6.5s6.5 2.9 6.5 6.5" />
    <path d="M16 4.6a3.5 3.5 0 0 1 0 6.8" /><path d="M18 13.8c2.1.8 3.5 2.9 3.5 5.2" />
  </Svg>
);
export const MoneyIcon = (p: Props) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M14.8 9.2c-.5-1-1.6-1.6-2.8-1.6-1.6 0-2.8.9-2.8 2.2 0 3 5.8 1.6 5.8 4.6 0 1.3-1.3 2.3-3 2.3-1.3 0-2.5-.6-3-1.7M12 6v1.6M12 16.7V18" />
  </Svg>
);
export const GaugeIcon = (p: Props) => (
  <Svg {...p}><path d="M4 16a8 8 0 1 1 16 0" /><path d="M12 16l4-5" /><path d="M3 20h18" /></Svg>
);
export const LinkIcon = (p: Props) => (
  <Svg {...p}>
    <path d="M10 14a4.5 4.5 0 0 0 6.4 0l3-3a4.5 4.5 0 0 0-6.4-6.4l-1 1" />
    <path d="M14 10a4.5 4.5 0 0 0-6.4 0l-3 3a4.5 4.5 0 0 0 6.4 6.4l1-1" />
  </Svg>
);
export const CopyIcon = (p: Props) => (
  <Svg {...p}>
    <rect x="8.5" y="8.5" width="12" height="12" rx="2.5" />
    <path d="M15.5 8.5V6a2.5 2.5 0 0 0-2.5-2.5H6A2.5 2.5 0 0 0 3.5 6v7A2.5 2.5 0 0 0 6 15.5h2.5" />
  </Svg>
);
export const PhotoIcon = (p: Props) => (
  <Svg {...p}><rect x="3.5" y="4.5" width="17" height="15" rx="2.5" /><circle cx="9" cy="10" r="1.8" /><path d="M20.5 16l-5-5L5 19.5" /></Svg>
);
export const PlusIcon = (p: Props) => <Svg {...p}><path d="M12 5v14M5 12h14" /></Svg>;
export const CheckIcon = (p: Props) => <Svg {...p}><path d="M5 12.5l4.5 4.5L19 7.5" /></Svg>;
export const ChevronIcon = (p: Props) => <Svg {...p}><path d="M6 9l6 6 6-6" /></Svg>;
export const LockIcon = (p: Props) => (
  <Svg {...p}><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></Svg>
);
export const UndoIcon = (p: Props) => <Svg {...p}><path d="M9 14L4 9l5-5" /><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11" /></Svg>;

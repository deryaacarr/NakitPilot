/**
 * NP-502 — responsive breakpoint audit targets.
 * Aligns with Tailwind defaults where possible; documents QA viewports.
 */
export const BREAKPOINTS = {
  xs: 375,
  smPhone: 430,
  md: 768,
  lg: 1024,
  laptop: 1366,
  desktop: 1440,
  wide: 1920,
  ultrawide: 2560,
} as const;

export type BreakpointName = keyof typeof BREAKPOINTS;

export const BREAKPOINT_ACCEPTANCE = [
  {
    width: BREAKPOINTS.wide,
    rule: "1920 px’de içerik gereksiz dar kalmamalı (max-width makul genişlikte).",
  },
  {
    width: BREAKPOINTS.ultrawide,
    rule: "Çok geniş ekranda satır uzunluğu kontrol edilmeli (measure / max-w-prose).",
  },
  {
    width: BREAKPOINTS.laptop,
    rule: "1366 px’de yatay taşma olmamalı.",
  },
  {
    width: BREAKPOINTS.xs,
    rule: "Mobilde ana aksiyonlar görünür olmalı.",
  },
] as const;

/** Content width strategy for page shells. */
export const CONTENT_WIDTH = {
  /** Dashboard / list / report — fill space up to ultrawide comfort */
  fluid: "max-w-[90rem]", // 1440px
  /** Detail / settings / form — readable column */
  reading: "max-w-5xl",
  /** Long body text */
  prose: "max-w-prose",
  /** Wizard */
  wizard: "max-w-3xl",
} as const;

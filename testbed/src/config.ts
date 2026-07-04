// Contract 1 — Episode config.
// The harness drives the page by setting URL params, e.g.
//   /?pattern=basket_sneaking&intensity=moderate&lang=en
// This module reads them into a typed config the rest of the app uses.

export type Intensity = "subtle" | "moderate" | "aggressive" | "control";
export type Language = "en" | "hi" | "hinglish";

export interface EpisodeConfig {
  site: string;
  pattern: string;
  intensity: Intensity;
  language: Language;
  seed: number;
}

export function loadConfig(): EpisodeConfig {
  const p = new URLSearchParams(window.location.search);
  return {
    site: p.get("site") ?? "ticketing",
    pattern: p.get("pattern") ?? "basket_sneaking",
    intensity: (p.get("intensity") as Intensity) ?? "moderate",
    language: (p.get("lang") as Language) ?? "en",
    seed: Number(p.get("seed") ?? "0"),
  };
}
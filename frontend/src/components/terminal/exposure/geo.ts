// Loosely typed bindings: @types for these packages may not be installed.
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore
import { geoNaturalEarth1, geoPath } from "d3-geo";
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore
import { feature } from "topojson-client";
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore
import worldTopo from "world-atlas/countries-110m.json";

import type { Signal } from "@/api/types";

export const MAP_W = 960;
export const MAP_H = 500;

export interface GeoFeature {
  id?: string | number;
  properties: { name: string };
  geometry: unknown;
}
interface Projection {
  fitSize(size: [number, number], obj: unknown): Projection;
}
interface PathGen {
  (f: unknown): string | null;
  centroid(f: unknown): [number, number];
}
const d3geo = { geoNaturalEarth1, geoPath } as unknown as {
  geoNaturalEarth1: () => Projection;
  geoPath: (p: Projection) => PathGen;
};
const topo = worldTopo as unknown as { objects: { countries: unknown } };
const toFeatures = feature as unknown as (t: unknown, o: unknown) => { features: GeoFeature[] };

export interface MapShape {
  key: string;
  name: string;
  d: string;
  cx: number;
  cy: number;
}

let cache: MapShape[] | null = null;
/** Country shapes projected once (geoNaturalEarth1 fitted to the viewBox). */
export function mapShapes(): MapShape[] {
  if (cache) return cache;
  const projection = d3geo.geoNaturalEarth1().fitSize([MAP_W, MAP_H], { type: "Sphere" });
  const path = d3geo.geoPath(projection);
  const feats = toFeatures(topo, topo.objects.countries).features;
  cache = feats.flatMap((f) => {
    const d = path(f);
    if (!d) return [];
    const [cx, cy] = path.centroid(f);
    return [{ key: norm(f.properties.name), name: f.properties.name, d, cx, cy }];
  });
  return cache;
}

export function norm(s: string): string {
  return s.toLowerCase().replace(/[’`]/g, "'").replace(/&/g, "and").replace(/\s+/g, " ").trim();
}

/** API-name (normalised) -> world-atlas name (normalised). */
const ALIAS: Record<string, string> = {
  "united states": "united states of america",
  usa: "united states of america",
  us: "united states of america",
  "u.s.": "united states of america",
  uk: "united kingdom",
  "great britain": "united kingdom",
  uae: "united arab emirates",
  "dr congo": "dem. rep. congo",
  "congo - kinshasa": "dem. rep. congo",
  "congo (drc)": "dem. rep. congo",
  "democratic republic of the congo": "dem. rep. congo",
  "congo - brazzaville": "congo",
  "republic of the congo": "congo",
  "congo (republic)": "congo",
  "bosnia and herzegovina": "bosnia and herz.",
  "central african republic": "central african rep.",
  "dominican republic": "dominican rep.",
  "south sudan": "s. sudan",
  "equatorial guinea": "eq. guinea",
  "western sahara": "w. sahara",
  "solomon islands": "solomon is.",
  "falkland islands": "falkland is.",
  "russian federation": "russia",
  "korea, republic of": "south korea",
  "republic of korea": "south korea",
  "korea, democratic people's republic of": "north korea",
  "ivory coast": "côte d'ivoire",
  "cote d'ivoire": "côte d'ivoire",
  türkiye: "turkey",
  turkiye: "turkey",
  "czech republic": "czechia",
  "trinidad and tobago": "trinidad and tobago",
  "myanmar (burma)": "myanmar",
  "palestinian territories": "palestine",
  "north macedonia": "macedonia",
  swaziland: "eswatini",
  "timor-leste": "timor-leste",
  "east timor": "timor-leste",
  vietnam: "vietnam",
  "viet nam": "vietnam",
  "lao people's democratic republic": "laos",
  "syrian arab republic": "syria",
  "iran, islamic republic of": "iran",
  "tanzania, united republic of": "tanzania",
};

/** Human display name for an API country value (ISO alpha-2 converted via Intl.DisplayNames). */
export function displayName(country: string): string {
  const c = country.trim();
  if (/^[A-Za-z]{2}$/.test(c) || /^[A-Za-z]{3}$/.test(c)) {
    try {
      const n = new Intl.DisplayNames(["en"], { type: "region" }).of(c.toUpperCase());
      if (n && n.toUpperCase() !== c.toUpperCase()) return n;
    } catch {
      /* alpha-3 not supported by this runtime: fall through to name match */
    }
  }
  return c;
}

/** Resolve an API country to a world-atlas feature key (or null when no shape exists). */
export function resolveKey(country: string, keys: Set<string>): string | null {
  const raw = norm(country);
  const disp = norm(displayName(country));
  for (const c of [raw, ALIAS[raw], disp, ALIAS[disp]]) if (c && keys.has(c)) return c;
  return null;
}

export interface Pin {
  signal: Signal;
  key: string;
  x: number;
  y: number;
}

function esc(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** A pin exists only when a known country's name appears as a word in the signal's headline or text. */
export function derivePins(signals: Signal[], countries: string[], shapes: MapShape[]): Pin[] {
  const byKey = new Map(shapes.map((s) => [s.key, s]));
  const keys = new Set(byKey.keys());
  const matchers: { re: RegExp; key: string; len: number }[] = [];
  for (const c of countries) {
    const key = resolveKey(c, keys);
    if (!key) continue;
    const names = new Set<string>([displayName(c)]);
    if (c.trim().length > 3) names.add(c.trim());
    for (const n of names)
      matchers.push({
        re: new RegExp(`(^|[^\\p{L}])${esc(n)}($|[^\\p{L}])`, "iu"),
        key,
        len: n.length,
      });
  }
  matchers.sort((a, b) => b.len - a.len);
  const seen = new Map<string, number>();
  const pins: Pin[] = [];
  for (const s of signals) {
    const hay = `${s.headline} ${s.text}`;
    const m = matchers.find((x) => x.re.test(hay));
    const shape = m ? byKey.get(m.key) : undefined;
    if (!m || !shape) continue;
    const k = seen.get(m.key) ?? 0;
    seen.set(m.key, k + 1);
    const ang = k * 2.4;
    const rad = k === 0 ? 0 : 5 + 2 * Math.floor(k / 6);
    pins.push({
      signal: s,
      key: m.key,
      x: shape.cx + Math.cos(ang) * rad,
      y: shape.cy + Math.sin(ang) * rad,
    });
    if (pins.length >= 60) break;
  }
  return pins;
}

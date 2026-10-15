// Shared, browser-safe geometry for the hero globe (WebGL + SVG fallback).

export const GLOBE_COLORS = {
  // WebGL can't read oklch tokens; these mirror --ink and --primary.
  ink: "#1c1b20",
  crimson: "#c8243a",
};

function seeded(seed: number) {
  let s = seed;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

export function fibonacciSphere(count: number, radius = 1): [number, number, number][] {
  const pts: [number, number, number][] = [];
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < count; i++) {
    const y = 1 - (i / (count - 1)) * 2;
    const r = Math.sqrt(1 - y * y);
    const theta = golden * i;
    pts.push([Math.cos(theta) * r * radius, y * radius, Math.sin(theta) * r * radius]);
  }
  return pts;
}

export function eventNodes(count = 40, radius = 1): [number, number, number][] {
  const rand = seeded(7);
  return Array.from({ length: count }, () => {
    const u = rand() * 2 - 1;
    const t = rand() * Math.PI * 2;
    const r = Math.sqrt(1 - u * u);
    return [Math.cos(t) * r * radius, u * radius, Math.sin(t) * r * radius];
  });
}

export function arcPairs(nodeCount: number, pairs = 12): [number, number][] {
  const rand = seeded(42);
  return Array.from({ length: pairs }, () => {
    const a = Math.floor(rand() * nodeCount);
    let b = Math.floor(rand() * nodeCount);
    if (b === a) b = (b + 1) % nodeCount;
    return [a, b];
  });
}

/** Great-circle points between a and b, lifted above the surface. */
export function greatCircle(
  a: [number, number, number],
  b: [number, number, number],
  segments = 48,
  lift = 0.25,
): [number, number, number][] {
  const dot = a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const omega = Math.acos(Math.min(1, Math.max(-1, dot)));
  const sin = Math.sin(omega) || 1;
  const out: [number, number, number][] = [];
  for (let i = 0; i <= segments; i++) {
    const t = i / segments;
    const k1 = Math.sin((1 - t) * omega) / sin;
    const k2 = Math.sin(t * omega) / sin;
    const h = 1 + Math.sin(Math.PI * t) * lift;
    out.push([
      (a[0] * k1 + b[0] * k2) * h,
      (a[1] * k1 + b[1] * k2) * h,
      (a[2] * k1 + b[2] * k2) * h,
    ]);
  }
  return out;
}

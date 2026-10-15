import { useReducedMotion } from "framer-motion";
import { lazy, Suspense, useEffect, useMemo, useState } from "react";

import { arcPairs, eventNodes, fibonacciSphere } from "./globe-data";

const GlobeCanvas = lazy(() => import("./globe-canvas"));

function StaticGlobe() {
  const dots = useMemo(() => fibonacciSphere(700).filter((p) => p[2] > 0), []);
  const nodes = useMemo(() => eventNodes(40).filter((p) => p[2] > 0), []);
  const all = useMemo(() => eventNodes(40), []);
  const arcs = useMemo(
    () => arcPairs(40, 12).filter(([a, b]) => all[a]![2] > 0 && all[b]![2] > 0),
    [all],
  );
  const s = 180;
  return (
    <svg
      viewBox="-200 -200 400 400"
      className="h-full w-full"
      role="img"
      aria-label="Globe of risk events"
    >
      <g className="fill-foreground" opacity={0.25}>
        {dots.map((p, i) => (
          <circle key={i} cx={p[0] * s} cy={-p[1] * s} r={1.1} />
        ))}
      </g>
      <g className="stroke-primary" fill="none" opacity={0.5} strokeDasharray="4 3">
        {arcs.map(([a, b], i) => {
          const A = all[a]!,
            B = all[b]!;
          const mx = ((A[0] + B[0]) / 2) * s * 1.3,
            my = (-(A[1] + B[1]) / 2) * s * 1.3;
          return (
            <path key={i} d={`M${A[0] * s},${-A[1] * s} Q${mx},${my} ${B[0] * s},${-B[1] * s}`} />
          );
        })}
      </g>
      <g className="fill-primary">
        {nodes.map((p, i) => (
          <circle key={i} cx={p[0] * s} cy={-p[1] * s} r={2.4} />
        ))}
      </g>
    </svg>
  );
}

export function HeroGlobe() {
  const reduceMotion = useReducedMotion();
  const [mode, setMode] = useState<"pending" | "static" | "webgl">("pending");

  useEffect(() => {
    const mobile = window.matchMedia("(max-width: 1023px), (pointer: coarse)").matches;
    setMode(mobile || reduceMotion ? "static" : "webgl");
  }, [reduceMotion]);

  if (mode === "pending") return <div className="h-full w-full" />;
  if (mode === "static") return <StaticGlobe />;
  return (
    <Suspense fallback={<StaticGlobe />}>
      <GlobeCanvas />
    </Suspense>
  );
}

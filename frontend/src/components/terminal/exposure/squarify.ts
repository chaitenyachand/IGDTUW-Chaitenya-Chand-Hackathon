export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

function worst(row: number[], side: number): number {
  const s = row.reduce((a, b) => a + b, 0);
  if (s <= 0) return Infinity;
  const mx = Math.max(...row);
  const mn = Math.min(...row);
  return Math.max((side * side * mx) / (s * s), (s * s) / (side * side * mn));
}

/** Squarified treemap. `values` must be positive and sorted descending; returns one rect per value. */
export function squarify(values: number[], W: number, H: number): Rect[] {
  const total = values.reduce((a, b) => a + b, 0);
  if (!values.length || total <= 0 || W <= 0 || H <= 0) return [];
  const areas = values.map((v) => (v / total) * W * H);
  const out: Rect[] = new Array(values.length);
  let x = 0;
  let y = 0;
  let w = W;
  let h = H;
  let i = 0;
  while (i < areas.length) {
    const side = Math.min(w, h);
    let j = i + 1;
    let row = [areas[i] ?? 0];
    while (j < areas.length) {
      const next = [...row, areas[j] ?? 0];
      if (worst(next, side) <= worst(row, side)) {
        row = next;
        j++;
      } else break;
    }
    const sum = row.reduce((a, b) => a + b, 0);
    const thick = side > 0 ? sum / side : 0;
    if (w >= h) {
      let cy = y;
      row.forEach((a, k) => {
        const hh = thick > 0 ? a / thick : 0;
        out[i + k] = { x, y: cy, w: thick, h: hh };
        cy += hh;
      });
      x += thick;
      w -= thick;
    } else {
      let cx = x;
      row.forEach((a, k) => {
        const ww = thick > 0 ? a / thick : 0;
        out[i + k] = { x: cx, y, w: ww, h: thick };
        cx += ww;
      });
      y += thick;
      h -= thick;
    }
    i = j;
  }
  return out;
}

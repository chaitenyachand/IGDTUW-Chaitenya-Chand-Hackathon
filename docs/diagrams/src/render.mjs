import { chromium } from "/tmp/claude-0/-home-claude/b99fafe6-dbf4-56b7-9d49-00a698c41949/scratchpad/fe/frontend/node_modules/@playwright/test/index.mjs";
import fs from "fs";
const [,, ...names] = process.argv;
const b = await chromium.launch({ args: ["--no-sandbox"] });
for (const n of names) {
  const svg = fs.readFileSync(n + ".svg", "utf8");
  const m = svg.match(/viewBox="-8 -4 (\d+) (\d+)"/); const w = +m[1], h = +m[2];
  const p = await b.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 3 });
  await p.setContent(`<body style="margin:0">${svg}</body>`);
  await p.screenshot({ path: n + ".png", clip: { x: 0, y: 0, width: w, height: h } });
  console.log("rendered", n, w * 3, h * 3);
}
await b.close();

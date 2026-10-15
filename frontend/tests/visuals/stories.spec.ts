import { expect, test, type Page } from "@playwright/test";

const STORIES = ["platform", "precedent", "modules", "stress-lab"] as const;

async function openLanding(page: Page) {
  await page.goto("/");
  await page.evaluate(() => sessionStorage.setItem("sentinel:preloaded", "1"));
  await page.reload();
  await page.evaluate(() => document.fonts.ready);
  const pinned = await page.evaluate(
    () => matchMedia("(min-width: 1024px) and (prefers-reduced-motion: no-preference)").matches,
  );
  if (pinned)
    await page.waitForFunction(() => document.documentElement.dataset["storyMotion"] === "ready");
  await page.waitForTimeout(400);
  return pinned;
}

async function scrollToY(page: Page, y: number) {
  await page.evaluate((top) => window.scrollTo(0, top), y);
  await page.waitForTimeout(900); // scrub smoothing settles
}

async function sectionTop(page: Page, id: string) {
  return page.evaluate((sid) => {
    const el = document.getElementById(sid);
    return el ? el.getBoundingClientRect().top + window.scrollY : 0;
  }, id);
}

/** Returns px by which any visible pinned stage escapes its own section. */
async function stageOverflow(page: Page) {
  return page.evaluate(() => {
    let worst = 0;
    document.querySelectorAll<HTMLElement>("[data-story-shell]").forEach((shell) => {
      const stage = shell.querySelector<HTMLElement>(".motion-story-stage");
      if (!stage || getComputedStyle(stage).display === "none") return;
      const s = shell.getBoundingClientRect();
      const r = stage.getBoundingClientRect();
      if (r.bottom < 0 || r.top > innerHeight) return;
      worst = Math.max(worst, s.top - r.top, r.bottom - s.bottom);
    });
    return Math.round(worst);
  });
}

const masks = (page: Page) => [page.locator("canvas"), page.locator("[data-slot='preview-media']")];

test.describe("story loading states", () => {
  for (const id of STORIES) {
    test(`${id} loads in a stable initial state`, async ({ page }) => {
      await openLanding(page);
      const top = await sectionTop(page, id);
      await scrollToY(page, top);
      expect(await stageOverflow(page)).toBeLessThanOrEqual(1);
      await expect(page).toHaveScreenshot(`${id}-enter.png`, { mask: masks(page) });
    });
  }
});

test.describe("section handoffs", () => {
  for (const id of STORIES) {
    test(`${id} hands off cleanly to the next section`, async ({ page }) => {
      await openLanding(page);
      const vh = page.viewportSize()?.height ?? 800;
      const top = await sectionTop(page, id);
      const height = await page.evaluate(
        (sid) => document.getElementById(sid)?.offsetHeight ?? 0,
        id,
      );
      // Just before the scene arrives, across its boundary, and while leaving.
      for (const y of [
        top - vh * 0.5,
        top - 4,
        top + 4,
        top + height - vh * 0.5,
        top + height - 4,
      ]) {
        await scrollToY(page, Math.max(0, y));
        expect(
          await stageOverflow(page),
          `stage escaped #${id} at y=${Math.round(y)}`,
        ).toBeLessThanOrEqual(1);
      }
      await scrollToY(page, top + height - vh * 0.5);
      await expect(page).toHaveScreenshot(`${id}-handoff.png`, { mask: masks(page) });
    });
  }

  test("full-page scroll never overlaps stages", async ({ page }) => {
    await openLanding(page);
    const total = await page.evaluate(() => document.documentElement.scrollHeight - innerHeight);
    const step = Math.round((page.viewportSize()?.height ?? 800) * 0.35);
    for (let y = 0; y <= total; y += step) {
      await page.evaluate((top) => window.scrollTo(0, top), y);
      await page.waitForTimeout(60);
      expect(await stageOverflow(page), `overlap at y=${y}`).toBeLessThanOrEqual(1);
    }
  });
});

import { useEffect, type RefObject } from "react";

/**
 * Shared GSAP loader for every scroll-driven landing scene.
 *
 * One loader, one refresh queue: pinned scenes are registered with an explicit
 * document order (refreshPriority), and layout shifts above them (fonts, images,
 * hero reveal) trigger a single debounced refresh so pin positions never go stale.
 */
export const STORY_MEDIA = "(min-width: 1024px) and (prefers-reduced-motion: no-preference)";

type GsapModule = typeof import("gsap");
type ScrollTriggerModule = typeof import("gsap/ScrollTrigger");
export type StoryMotion = {
  gsap: GsapModule["default"];
  ScrollTrigger: ScrollTriggerModule["ScrollTrigger"];
};

let loader: Promise<StoryMotion> | null = null;
let refreshTimer: number | undefined;
let lastHeight = 0;

function markReady(state: "pending" | "ready") {
  document.documentElement.dataset["storyMotion"] = state;
}

export function queueStoryRefresh() {
  if (typeof window === "undefined" || !loader) return;
  markReady("pending");
  window.clearTimeout(refreshTimer);
  refreshTimer = window.setTimeout(() => {
    void loader?.then(({ ScrollTrigger }) => {
      ScrollTrigger.sort();
      ScrollTrigger.refresh();
      lastHeight = document.documentElement.scrollHeight;
      markReady("ready");
    });
  }, 120);
}

export function loadStoryMotion() {
  if (!loader) {
    loader = Promise.all([import("gsap"), import("gsap/ScrollTrigger")]).then(
      ([{ default: gsap }, { ScrollTrigger }]) => {
        gsap.registerPlugin(ScrollTrigger);
        ScrollTrigger.config({ ignoreMobileResize: true });
        // Anything that changes layout above a pinned scene invalidates its start position.
        void document.fonts?.ready.then(queueStoryRefresh);
        window.addEventListener("load", queueStoryRefresh, { once: true });
        const observer = new ResizeObserver(() => {
          if (Math.abs(document.documentElement.scrollHeight - lastHeight) > 2) queueStoryRefresh();
        });
        observer.observe(document.body);
        return { gsap, ScrollTrigger };
      },
    );
  }
  return loader;
}

/**
 * Registers a scene. `order` is the scene's position on the page (0 = highest);
 * earlier scenes refresh first so later pins account for their spacing.
 * `setup` runs only on desktop with motion allowed and is fully reverted otherwise.
 */
export function useStoryScene(
  ref: RefObject<HTMLElement | null>,
  order: number,
  setup: (motion: StoryMotion & { root: HTMLElement; priority: number }) => void,
  media: string = STORY_MEDIA,
) {
  useEffect(() => {
    let active = true;
    let revert: (() => void) | undefined;
    void loadStoryMotion().then((motion) => {
      const root = ref.current;
      if (!active || !root) return;
      const mm = motion.gsap.matchMedia();
      revert = () => mm.revert();
      mm.add(media, () => {
        setup({ ...motion, root, priority: 100 - order });
      });
      queueStoryRefresh();
    });
    return () => {
      active = false;
      revert?.();
      queueStoryRefresh();
    };
    // setup is defined inline per scene and intentionally registered once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}

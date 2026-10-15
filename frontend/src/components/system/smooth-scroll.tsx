import { useEffect } from "react";

type LenisLike = {
  scrollTo: (target: HTMLElement | string, options?: { offset?: number }) => void;
};
let lenisInstance: LenisLike | null = null;

export function scrollToTarget(selector: string) {
  const el = document.querySelector<HTMLElement>(selector);
  if (!el) return;
  if (lenisInstance) lenisInstance.scrollTo(el, { offset: -40 });
  else
    el.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
    });
}

export function SmoothScroll() {
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    let cleanup = () => {};
    let active = true;

    void Promise.all([import("lenis"), import("gsap"), import("gsap/ScrollTrigger")]).then(
      ([{ default: Lenis }, { default: gsap }, { ScrollTrigger }]) => {
        if (!active) return;
        gsap.registerPlugin(ScrollTrigger);
        const lenis = new Lenis({ duration: 1.1, smoothWheel: true });
        lenisInstance = lenis;
        const update = (time: number) => lenis.raf(time * 1000);
        lenis.on("scroll", ScrollTrigger.update);
        gsap.ticker.add(update);
        gsap.ticker.lagSmoothing(0);
        cleanup = () => {
          gsap.ticker.remove(update);
          lenis.destroy();
          lenisInstance = null;
        };
      },
    );

    return () => {
      active = false;
      cleanup();
    };
  }, []);

  return null;
}

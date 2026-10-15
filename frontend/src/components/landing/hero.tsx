import { Link } from "@tanstack/react-router";
import { motion, useReducedMotion } from "framer-motion";
import { ArrowDown, ArrowUpRight } from "lucide-react";

import { Magnetic } from "@/components/motion/magnetic";
import { SplitWords } from "@/components/motion/split-words";
import { scrollToTarget } from "@/components/system/smooth-scroll";
import { Button } from "@/components/ui/button";

import { HeroGlobe } from "./hero-globe";

export function Hero({ ready }: { ready: boolean }) {
  const reduceMotion = useReducedMotion();
  const fade = (delay: number) => ({
    initial: { opacity: 0, y: 16 },
    animate: ready ? { opacity: 1, y: 0 } : { opacity: 0, y: 16 },
    transition: {
      duration: 0.8,
      delay: reduceMotion ? 0 : delay,
      ease: [0.22, 1, 0.36, 1] as const,
    },
  });

  return (
    <section className="relative mx-auto grid min-h-screen max-w-[1600px] items-center gap-10 px-5 pt-[74px] lg:grid-cols-2 lg:px-10">
      <div className="relative z-10 py-12">
        <motion.p
          {...fade(0)}
          className="font-mono text-[11px] uppercase tracking-label text-secondary-foreground"
        >
          Risk intelligence platform
        </motion.p>
        <h1 className="mt-6 font-display text-[clamp(3rem,7vw,7.25rem)] leading-[0.95] tracking-[-0.01em]">
          {ready ? (
            <SplitWords
              text="Risk intelligence with a memory."
              emphasis={["memory"]}
              emphasisClassName="italic text-primary"
              delay={0.1}
            />
          ) : (
            <span className="opacity-0">Risk intelligence with a memory.</span>
          )}
        </h1>
        <motion.p {...fade(0.5)} className="mt-8 max-w-xl text-lg text-secondary-foreground">
          SENTINEL reads the news, scores the risk, and shows you what happened the last time. Then
          it acts on your portfolio.
        </motion.p>
        <motion.div {...fade(0.65)} className="mt-10 flex flex-wrap items-center gap-8">
          <Magnetic>
            <Button
              asChild
              size="lg"
              className="h-12 rounded-none px-6 font-mono text-xs uppercase tracking-label shadow-none hover:bg-primary-hover"
            >
              <Link to="/app">
                Open Terminal <ArrowUpRight />
              </Link>
            </Button>
          </Magnetic>
          <button
            type="button"
            onClick={() => scrollToTarget("#story")}
            className="group inline-flex items-center gap-2 text-sm font-medium text-foreground transition-colors hover:text-primary"
          >
            See how it works
            <ArrowDown className="size-4 transition-transform duration-500 group-hover:translate-y-0.5" />
          </button>
        </motion.div>
      </div>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: ready ? 1 : 0 }}
        transition={{ duration: 1.2, delay: 0.3 }}
        className="relative aspect-square w-full max-w-[720px] justify-self-center"
      >
        <HeroGlobe />
      </motion.div>
    </section>
  );
}

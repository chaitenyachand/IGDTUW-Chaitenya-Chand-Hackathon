import { Link } from "@tanstack/react-router";
import { motion, useReducedMotion } from "framer-motion";
import { Menu, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { TerminalLink } from "@/components/system/terminal-transition";
import { Button } from "@/components/ui/button";

const navigation = [
  { label: "Platform", hash: "platform" },
  { label: "Precedent", hash: "precedent" },
  { label: "Modules", hash: "modules" },
  { label: "Architecture", hash: "architecture" },
];

export function SiteNav() {
  const [hidden, setHidden] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const lastY = useRef(0);
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    let ticking = false;
    const onScroll = () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(() => {
        const current = window.scrollY;
        setHidden(current > 96 && current > lastY.current && !menuOpen);
        lastY.current = current;
        ticking = false;
      });
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [menuOpen]);

  return (
    <motion.header
      className="fixed inset-x-0 top-0 z-50 border-b border-hairline/70 bg-paper/80 backdrop-blur-xl"
      animate={{ y: hidden && !reduceMotion ? "-100%" : 0 }}
      transition={{ duration: reduceMotion ? 0.2 : 0.7, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="mx-auto flex h-[74px] max-w-[1600px] items-center justify-between px-5 lg:px-10">
        <Link
          to="/"
          className="font-sans text-[15px] font-bold tracking-[0.16em] text-foreground"
          aria-label="SENTINEL home"
        >
          SENTINEL<span className="text-primary">.</span>
        </Link>

        <nav className="hidden items-center gap-8 lg:flex" aria-label="Primary navigation">
          {navigation.map((item) => (
            <Link
              key={item.label}
              to="/"
              hash={item.hash}
              className="text-xs font-medium text-secondary-foreground transition-colors duration-700 hover:text-primary"
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="hidden lg:block">
          <TerminalLink />
        </div>

        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden"
          onClick={() => setMenuOpen((open) => !open)}
          aria-label={menuOpen ? "Close menu" : "Open menu"}
          aria-expanded={menuOpen}
        >
          {menuOpen ? <X /> : <Menu />}
        </Button>
      </div>

      {menuOpen ? (
        <motion.nav
          className="border-t border-hairline bg-paper px-5 py-7 lg:hidden"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          aria-label="Mobile navigation"
        >
          <div className="flex flex-col">
            {navigation.map((item) => (
              <Link
                key={item.label}
                to="/"
                hash={item.hash}
                onClick={() => setMenuOpen(false)}
                className="border-b border-hairline py-4 font-display text-3xl"
              >
                {item.label}
              </Link>
            ))}
            <div className="mt-7" onClick={() => setMenuOpen(false)}>
              <TerminalLink />
            </div>
          </div>
        </motion.nav>
      ) : null}
    </motion.header>
  );
}

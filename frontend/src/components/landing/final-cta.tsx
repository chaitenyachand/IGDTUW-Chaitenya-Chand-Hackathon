import { TerminalLink } from "@/components/system/terminal-transition";

export function FinalCta() {
  return (
    <section className="flex min-h-[70svh] items-center bg-paper py-24 text-foreground">
      <div className="mx-auto w-full max-w-[1500px] px-5 lg:px-10">
        <p className="font-mono text-xs uppercase tracking-label text-primary">SENTINEL</p>
        <h2 className="mt-8 max-w-[1200px] font-display text-[clamp(3.5rem,8vw,8rem)] leading-[0.95]">
          Start with what’s <em className="text-primary">coming.</em>
        </h2>
        <div className="mt-12">
          <TerminalLink large />
        </div>
      </div>
    </section>
  );
}

import { ArrowDown, ArrowRight } from "lucide-react";

function Node({
  label,
  index,
  featured = false,
}: {
  label: string;
  index: string;
  featured?: boolean;
}) {
  return (
    <div
      className={`architecture-node relative z-10 flex min-h-24 flex-1 flex-col justify-center border px-5 py-5 lg:min-h-36 lg:px-7 ${featured ? "border-primary bg-paper" : "border-hairline bg-paper"}`}
    >
      <span className="font-mono text-[10px] text-primary">{index}</span>
      <span className="mt-2 font-display text-2xl leading-none lg:text-3xl">{label}</span>
    </div>
  );
}

function Connector() {
  return (
    <div
      className="architecture-connector relative z-10 flex h-12 shrink-0 items-center justify-center text-primary lg:h-auto lg:w-[8%]"
      aria-hidden="true"
    >
      <span className="absolute left-1/2 top-0 h-full w-px bg-hairline lg:left-0 lg:top-1/2 lg:h-px lg:w-full" />
      <span className="architecture-pulse absolute left-1/2 top-0 size-1.5 -translate-x-1/2 rounded-full bg-primary shadow-[0_0_12px_var(--primary)] lg:left-0 lg:top-1/2 lg:-translate-y-1/2 lg:translate-x-0" />
      <ArrowDown className="absolute bottom-0 size-3 lg:hidden" />
      <ArrowRight className="absolute right-0 hidden size-3 lg:block" />
    </div>
  );
}

export function ArchitectureFlow() {
  return (
    <section
      id="architecture"
      className="overflow-hidden bg-surface py-24 text-foreground lg:py-36"
    >
      <div className="mx-auto max-w-[1500px] px-5 lg:px-10">
        <p className="font-mono text-xs uppercase tracking-label text-primary">Architecture</p>
        <h2 className="mt-6 max-w-4xl font-display text-section leading-none">
          From the first signal to the <em className="text-primary">next move.</em>
        </h2>
        <div className="mt-16 flex flex-col items-stretch lg:mt-24 lg:flex-row lg:items-center">
          <Node index="01" label="Sources" />
          <Connector />
          <Node index="02" label="NLP Engine" />
          <Connector />
          <Node index="03" label="PRECEDENT" featured />
          <Connector />
          <div className="relative z-10 flex flex-1 flex-col gap-3">
            <Node index="04A" label="Index" />
            <Node index="04B" label="Stress Lab" />
          </div>
        </div>
        <div className="mt-10 flex items-center gap-4 font-mono text-[10px] uppercase tracking-label text-secondary-foreground">
          <span className="h-px w-9 bg-primary" /> Signal path{" "}
          <span className="ml-auto">Sample illustration</span>
        </div>
      </div>
    </section>
  );
}

import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";

import { Hero } from "@/components/landing/hero";
import { ArchitectureFlow } from "@/components/landing/architecture-flow";
import { FinalCta } from "@/components/landing/final-cta";
import { ModulesScene } from "@/components/landing/modules-scene";
import { Preloader } from "@/components/landing/preloader";
import { ProductPreview } from "@/components/landing/product-preview";
import { IntelligenceStory, PrecedentStory } from "@/components/landing/story-scenes";
import { StressLab } from "@/components/landing/stress-lab";
import { TrustGrid } from "@/components/landing/trust-grid";
import { SiteNav } from "@/components/site-nav";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "SENTINEL — Risk intelligence with a memory" },
      {
        name: "description",
        content:
          "SENTINEL reads the news, scores the risk, and shows you what happened the last time. Then it acts on your portfolio.",
      },
      { property: "og:title", content: "SENTINEL — Risk intelligence with a memory" },
      {
        property: "og:description",
        content: "News-driven risk scoring with historical precedent, wired into your portfolio.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

function Index() {
  const [ready, setReady] = useState(false);
  return (
    <div className="paper-grain min-h-screen bg-paper text-foreground">
      <Preloader onDone={() => setReady(true)} />
      <SiteNav />
      <main>
        <Hero ready={ready} />
        <div className="pb-32">
          <ProductPreview />
        </div>
        <IntelligenceStory />
        <PrecedentStory />
        <ModulesScene />
        <StressLab />
        <TrustGrid />
        <ArchitectureFlow />
        <FinalCta />
      </main>
    </div>
  );
}

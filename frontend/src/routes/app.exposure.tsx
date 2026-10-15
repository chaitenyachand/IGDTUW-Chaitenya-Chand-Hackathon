import { createFileRoute } from "@tanstack/react-router";

import { ContagionGraph } from "@/components/terminal/exposure/graph";
import { SectorTreemap } from "@/components/terminal/exposure/treemap";
import { WorldMap } from "@/components/terminal/exposure/world-map";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export const Route = createFileRoute("/app/exposure")({
  head: () => ({ meta: [{ title: "Exposure — SENTINEL Terminal" }] }),
  component: ExposureScreen,
});

function ExposureScreen() {
  return (
    <div className="p-4 text-[13px]">
      <Tabs defaultValue="map">
        <TabsList>
          <TabsTrigger value="map">World Map</TabsTrigger>
          <TabsTrigger value="graph">Contagion Graph</TabsTrigger>
          <TabsTrigger value="treemap">Sector Treemap</TabsTrigger>
        </TabsList>
        <TabsContent value="map" className="mt-3">
          <WorldMap />
        </TabsContent>
        <TabsContent value="graph" className="mt-3">
          <ContagionGraph />
        </TabsContent>
        <TabsContent value="treemap" className="mt-3">
          <SectorTreemap />
        </TabsContent>
      </Tabs>
    </div>
  );
}

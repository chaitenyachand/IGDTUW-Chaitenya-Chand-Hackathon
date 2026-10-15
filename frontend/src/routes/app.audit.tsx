import { createFileRoute } from "@tanstack/react-router";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AlertFeed, RulesList } from "@/components/terminal/audit/alerts";
import { Ledger } from "@/components/terminal/audit/ledger";

export const Route = createFileRoute("/app/audit")({
  head: () => ({ meta: [{ title: "Audit & Alerts — SENTINEL Terminal" }] }),
  component: AuditPage,
});

function AuditPage() {
  return (
    <div className="p-4 text-[13px] lg:p-6">
      <Tabs defaultValue="ledger">
        <TabsList>
          <TabsTrigger value="ledger">Audit Ledger</TabsTrigger>
          <TabsTrigger value="alerts">Alerts</TabsTrigger>
        </TabsList>
        <TabsContent value="ledger" className="mt-3">
          <Ledger />
        </TabsContent>
        <TabsContent value="alerts" className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2">
          <RulesList />
          <AlertFeed />
        </TabsContent>
      </Tabs>
    </div>
  );
}

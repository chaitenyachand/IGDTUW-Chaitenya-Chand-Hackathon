import { createFileRoute } from "@tanstack/react-router";

import { EmptyState } from "@/components/terminal/kit";

export const Route = createFileRoute("/app/$")({
  head: () => ({ meta: [{ title: "Not found — SENTINEL Terminal" }] }),
  component: () => (
    <div className="p-6">
      <EmptyState
        title="Page not found"
        hint="Use the left rail or press Ctrl K to jump to a screen."
      />
    </div>
  ),
});

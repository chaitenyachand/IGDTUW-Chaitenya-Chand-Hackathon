import { Outlet, createFileRoute } from "@tanstack/react-router";

import { TerminalShell } from "@/components/terminal/shell";

export const Route = createFileRoute("/app")({
  head: () => ({
    meta: [
      { title: "Terminal — SENTINEL" },
      { name: "description", content: "SENTINEL intelligence terminal." },
      { property: "og:title", content: "Terminal — SENTINEL" },
      { property: "og:description", content: "SENTINEL intelligence terminal." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: TerminalLayout,
});

function TerminalLayout() {
  return (
    <TerminalShell>
      <Outlet />
    </TerminalShell>
  );
}

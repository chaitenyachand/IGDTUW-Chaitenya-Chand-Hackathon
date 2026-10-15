import type { ReactNode } from "react";

import { useModelMetrics } from "@/api/client";
import type { ModelMetrics } from "@/api/types";
import { Panel, QueryBoundary, SkeletonBlock } from "@/components/terminal/kit";

/** Panel bound to GET /api/model/metrics with skeleton / error / provenance handled. */
export function MetricsPanel({
  title,
  info,
  className,
  isEmpty,
  emptyTitle,
  children,
}: {
  title: ReactNode;
  info: ReactNode;
  className?: string | undefined;
  isEmpty?: ((m: ModelMetrics) => boolean) | undefined;
  emptyTitle?: string | undefined;
  children: (m: ModelMetrics) => ReactNode;
}) {
  const q = useModelMetrics();
  return (
    <Panel title={title} info={info} source={q.data?.meta.source} className={className}>
      <QueryBoundary
        query={q}
        endpoint="GET /api/model/metrics"
        skeleton={<SkeletonBlock className="h-52" />}
        isEmpty={isEmpty ? (env) => isEmpty(env.data) : undefined}
        emptyTitle={emptyTitle}
      >
        {(env) => children(env.data)}
      </QueryBoundary>
    </Panel>
  );
}

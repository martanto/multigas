import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Job } from "@/lib/api";
import { Button } from "@/lib/ui/button";
import { Progress } from "@/lib/ui/progress";
import { useEffect, useRef } from "react";

export function Jobs({ onDataset }: { onDataset: (id: string) => void }) {
  const cache = useQueryClient(),
    seen = useRef(new Set<string>()),
    initialized = useRef(false);
  const { data: jobs = [], isFetched } = useQuery({
    queryKey: ["jobs"],
    queryFn: () => api<Job[]>("/jobs"),
    refetchInterval: 1500,
  });
  useEffect(() => {
    if (!initialized.current && isFetched) {
      for (const job of jobs)
        if (job.status === "complete") seen.current.add(job.id);
      initialized.current = true;
      return;
    }
    for (const job of jobs) {
      if (job.status === "complete" && !seen.current.has(job.id)) {
        seen.current.add(job.id);
        void cache.invalidateQueries({ queryKey: ["datasets"] });
        if (job.result?.dataset) onDataset(job.result.dataset);
      }
    }
  }, [jobs, cache, onDataset, isFetched]);
  const active = jobs.filter((job) =>
    ["queued", "running", "cancelling"].includes(job.status),
  );
  const latest = jobs
    .filter((job) => !["queued", "running", "cancelling"].includes(job.status))
    .slice(-1);
  const visible = [...active, ...latest].reverse();
  return visible.length ? (
    <section aria-label="Recent jobs" className="surface divide-y">
      {visible.map((job) => (
        <div
          key={job.id}
          className="px-4 py-3 flex flex-wrap items-center justify-between gap-3 text-sm"
        >
          <div className="min-w-0 flex-1">
            <span className="font-medium capitalize">
              {job.kind} · {job.status}
            </span>
            {(job.message || job.status === "complete") && (
              <p className="text-xs text-muted-foreground mt-1">
                {job.status === "complete"
                  ? job.kind === "import"
                    ? "Dataset ready for analysis."
                    : "Export and reproducibility manifest ready."
                  : job.message}
              </p>
            )}
            {job.error && (
              <p role="alert" className="text-xs text-destructive mt-1">
                {job.error}
              </p>
            )}
            {["running", "queued", "cancelling"].includes(job.status) && (
              <Progress
                className="mt-2"
                value={job.progress * 100}
                aria-label={`${job.kind} progress`}
              />
            )}
          </div>
          {["queued", "running"].includes(job.status) && (
            <Button
              size="sm"
              variant="outline"
              onClick={() =>
                void api(`/jobs/${job.id}/cancel`, {}).then(() =>
                  cache.invalidateQueries({ queryKey: ["jobs"] }),
                )
              }
            >
              Cancel
            </Button>
          )}
          {["failed", "interrupted", "cancelled"].includes(job.status) && (
            <Button
              size="sm"
              variant="outline"
              onClick={() =>
                void api(`/jobs/${job.id}/retry`, {}).then(() =>
                  cache.invalidateQueries({ queryKey: ["jobs"] }),
                )
              }
            >
              Retry
            </Button>
          )}
          {job.result?.artifact && (
            <div className="flex gap-3 text-primary underline underline-offset-4">
              <a href={`/api/v1/downloads/${job.result.artifact}`}>Download</a>
              <a
                href={`/api/v1/downloads/${job.result.artifact}?manifest=true`}
              >
                Manifest
              </a>
            </div>
          )}
        </div>
      ))}
    </section>
  ) : null;
}

import { RecordBatchReader, tableFromIPC } from "apache-arrow";
import type { components } from "./generated/api";
export type Analysis = Omit<
  components["schemas"]["AnalysisSpec"],
  "ratio_source"
> & { ratio_source?: "onboard" | "calculated" };
export type ExportSpec = components["schemas"]["ExportSpec"];
export type Rule = components["schemas"]["Filter"];
export type Day = {
  date: string;
  records: number;
  expected: number | null;
  completeness: number | null;
};
export type Dataset = {
  id: string;
  station: string;
  source: string;
  checksum: string;
  created: string;
  mode: string;
  columns: string[];
  numeric_columns: string[];
  records: number;
  manifest: Day[];
  units: Record<string, string>;
  normalization: Record<string, string | number | boolean>;
};
export type Panel = {
  id: string;
  label: string;
  columns: string[];
  colors: string[];
  unit: string;
};
export type Staged = {
  id: string;
  name: string;
  size: number;
  preview: {
    format: string;
    columns: string[];
    units: Record<string, string>;
    sample: string[][];
    station: string;
    timestamp: string;
    preliminary: boolean;
  };
};
export type Job = {
  id: string;
  kind: string;
  status: string;
  progress: number;
  message?: string;
  error?: string;
  result?: { dataset?: string; artifact?: string };
};
export type View = {
  id: string;
  name: string;
  analysis: Analysis;
  arrangement: string[];
  unavailable?: string;
};
export type Stats = {
  filtered_records: number;
  channels: Record<
    string,
    {
      valid: number;
      validity: number | null;
      min: number | null;
      max: number | null;
      mean: number | null;
    }
  >;
  provenance: Record<
    string,
    { source: string; unit: string; formula?: string; conversion?: string }
  >;
  caveat: string;
};
export type Series = {
  channel: string;
  points: Float64Array;
  source: number;
  rendered: number;
  valid: number;
};

export async function api<T>(
  path: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers:
      body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw new Error(
      typeof error.detail === "string"
        ? error.detail
        : JSON.stringify(error.detail),
    );
  }
  return response.json();
}
async function fetchStream(
  spec: Analysis,
  signal?: AbortSignal,
  onProgress?: (loaded: number, total: number) => void,
): Promise<Series[]> {
  const response = await fetch("/api/v1/series/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(spec),
    signal,
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Chart request failed");
  }
  if (!response.body) throw new Error("Streaming response unavailable");
  const count = Number(response.headers.get("X-Source-Count") || 0);
  const groups = new Map<string, Series>();
  const reader = await RecordBatchReader.from(response.body);
  let reportedAt = 0;
  for await (const batch of reader) {
    const timestamps = batch.getChild("timestamp")!;
    for (const field of batch.schema.fields) {
      if (field.name === "timestamp") continue;
      if (!groups.has(field.name))
        groups.set(field.name, {
          channel: field.name,
          points: new Float64Array(count * 2),
          source: count,
          rendered: 0,
          valid: 0,
        });
      const series = groups.get(field.name)!,
        values = batch.getChild(field.name)!;
      for (let i = 0; i < batch.numRows; i++) {
        const value = values.get(i);
        const offset = series.rendered * 2;
        series.points[offset] = Number(timestamps.get(i));
        series.points[offset + 1] = value === null ? NaN : Number(value);
        if (value !== null) series.valid++;
        series.rendered++;
      }
    }
    const loaded = Math.max(0, ...[...groups.values()].map((s) => s.rendered));
    if (performance.now() - reportedAt > 200 || loaded === count) {
      onProgress?.(loaded, count);
      reportedAt = performance.now();
    }
    await new Promise<void>((resolve) => setTimeout(resolve, 0));
  }
  if ([...groups.values()].some((s) => s.rendered !== count))
    throw new Error("The plot stream ended early. Retry the analysis.");
  return [...groups.values()];
}
export async function fetchSeries(
  spec: Analysis,
  signal?: AbortSignal,
  onProgress?: (loaded: number, total: number) => void,
): Promise<Series[]> {
  try {
    return await fetchStream(spec, signal, onProgress);
  } catch (error) {
    if (signal?.aborted) throw error;
    // Preserve full-resolution plotting while an older local API finishes an
    // active import before its next restart. Both transports include every row.
    const groups = new Map<string, Series>();
    let offset = 0,
      total = 0;
    do {
      const response = await fetch(
        `/api/v1/series?offset=${offset}&limit=8000`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(spec),
          signal,
        },
      );
      if (!response.ok) {
        const body = await response.json();
        throw new Error(
          body.detail || "Chart request failed. Retry the analysis.",
        );
      }
      const table = tableFromIPC(new Uint8Array(await response.arrayBuffer()));
      for (const row of table.toArray()) {
        total = Number(row.source_count);
        if (!groups.has(row.channel))
          groups.set(row.channel, {
            channel: row.channel,
            points: new Float64Array(total * 2),
            source: total,
            rendered: 0,
            valid: 0,
          });
        const series = groups.get(row.channel)!,
          index = series.rendered * 2;
        series.points[index] = Date.parse(row.timestamp);
        series.points[index + 1] = row.value === null ? NaN : row.value;
        series.rendered++;
        if (row.value !== null) series.valid++;
      }
      offset += 8000;
      onProgress?.(Math.min(offset, total), total);
    } while (offset < total);
    if ([...groups.values()].some((s) => s.rendered !== total))
      throw new Error("The plot response ended early. Retry the analysis.");
    return [...groups.values()];
  }
}
export function upload(
  file: File,
  onProgress: (percent: number) => void,
  signal: AbortSignal,
): Promise<Staged> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open(
      "POST",
      `/api/v1/imports/preview?filename=${encodeURIComponent(file.name)}`,
    );
    request.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress((e.loaded / e.total) * 100);
    };
    request.onload = () => {
      try {
        const body = JSON.parse(request.responseText);
        if (request.status >= 400) reject(new Error(body.detail));
        else resolve(body);
      } catch {
        reject(new Error("Invalid upload response"));
      }
    };
    request.onerror = () =>
      reject(new Error("Upload failed. Check the local API and try again."));
    request.onabort = () => reject(new Error("Upload cancelled"));
    signal.addEventListener("abort", () => request.abort(), { once: true });
    request.send(file);
  });
}
export const number = (value: number | null | undefined, digits = 2) =>
  value == null
    ? "—"
    : new Intl.NumberFormat("en", { maximumFractionDigits: digits }).format(
        value,
      );

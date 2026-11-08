import { useState } from "react";
import { Download } from "lucide-react";
import { api, type Analysis, type Panel, type Job } from "@/lib/api";
import { Button } from "@/lib/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogTrigger,
} from "@/lib/ui/dialog";
import { Field, FieldGroup, FieldLabel } from "@/lib/ui/field";
import { Input } from "@/lib/ui/input";
import { Alert, AlertDescription } from "@/lib/ui/alert";

export function ExportDialog({
  analysis,
  panels,
  onJob,
}: {
  analysis: Analysis;
  panels: Panel[];
  onJob: (job: Job) => void;
}) {
  const [open, setOpen] = useState(false),
    [kind, setKind] = useState("figure"),
    [format, setFormat] = useState("png"),
    [width, setWidth] = useState(10),
    [height, setHeight] = useState(16),
    [dpi, setDpi] = useState(300),
    [selected, setSelected] = useState<string[]>(),
    [limits, setLimits] = useState<Record<string, [string, string]>>({}),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const active =
    selected !== undefined
      ? selected
      : analysis.panels?.length
        ? analysis.panels
        : panels.map((p) => p.id);
  const submit = async () => {
    setError("");
    if (kind === "figure" && active.length === 0) {
      setError("Select at least one panel.");
      return;
    }
    setBusy(true);
    try {
      const y_limits = Object.fromEntries(
        Object.entries(limits)
          .filter(([, v]) => v[0] !== "" && v[1] !== "")
          .map(([k, v]) => [k, v.map(Number)]),
      );
      const job = await api<Job>("/exports", {
        ...analysis,
        channels: kind === "figure" ? [] : analysis.channels,
        kind,
        format,
        width,
        height,
        dpi,
        panels: active,
        y_limits,
      });
      onJob(job);
      setOpen(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline">
          <Download data-icon="inline-start" />
          Export
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Export analysis</DialogTitle>
          <DialogDescription>
            Exports include a downloadable reproducibility manifest. Data
            exports retain every filtered observation.
          </DialogDescription>
        </DialogHeader>
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="export-kind">Export type</FieldLabel>
            <select
              id="export-kind"
              value={kind}
              onChange={(e) => setKind(e.target.value)}
            >
              <option value="figure">
                Scientific figure · MultiGas summary
              </option>
              <option value="csv">Full-resolution CSV</option>
              <option value="zip">Daily CSV ZIP · selected UTC range</option>
            </select>
          </Field>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field>
              <FieldLabel htmlFor="export-start">Start (UTC)</FieldLabel>
              <Input
                id="export-start"
                value={analysis.start || "Entire dataset"}
                readOnly
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="export-end">End (UTC)</FieldLabel>
              <Input
                id="export-end"
                value={analysis.end || "Entire dataset"}
                readOnly
              />
            </Field>
          </div>
          {kind === "figure" && (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <Field>
                  <FieldLabel htmlFor="format">Format</FieldLabel>
                  <select
                    id="format"
                    value={format}
                    onChange={(e) => setFormat(e.target.value)}
                  >
                    {["png", "pdf", "svg"].map((f) => (
                      <option key={f}>{f}</option>
                    ))}
                  </select>
                </Field>
                <Field>
                  <FieldLabel htmlFor="width">Width (in)</FieldLabel>
                  <Input
                    id="width"
                    type="number"
                    min={1}
                    max={30}
                    value={width}
                    onChange={(e) => setWidth(Number(e.target.value))}
                  />
                </Field>
                <Field>
                  <FieldLabel htmlFor="height">Height (in)</FieldLabel>
                  <Input
                    id="height"
                    type="number"
                    min={1}
                    max={40}
                    value={height}
                    onChange={(e) => setHeight(Number(e.target.value))}
                  />
                </Field>
                <Field>
                  <FieldLabel htmlFor="dpi">DPI</FieldLabel>
                  <Input
                    id="dpi"
                    type="number"
                    min={50}
                    max={600}
                    value={dpi}
                    onChange={(e) => setDpi(Number(e.target.value))}
                  />
                </Field>
              </div>
              <fieldset className="flex flex-col gap-3">
                <legend className="text-sm font-medium pb-2">
                  Panels and optional y-limits
                </legend>
                {panels.map((p) => (
                  <div
                    key={p.id}
                    className="flex flex-wrap items-center justify-between gap-2"
                  >
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={active.includes(p.id)}
                        onChange={() =>
                          setSelected(
                            active.includes(p.id)
                              ? active.filter((id) => id !== p.id)
                              : [...active, p.id],
                          )
                        }
                      />
                      {p.label}
                    </label>
                    <div className="flex gap-2">
                      <Input
                        className="w-24"
                        aria-label={`${p.label} minimum`}
                        type="number"
                        placeholder="Auto min"
                        value={limits[p.id]?.[0] || ""}
                        onChange={(e) =>
                          setLimits({
                            ...limits,
                            [p.id]: [e.target.value, limits[p.id]?.[1] || ""],
                          })
                        }
                      />
                      <Input
                        className="w-24"
                        aria-label={`${p.label} maximum`}
                        type="number"
                        placeholder="Auto max"
                        value={limits[p.id]?.[1] || ""}
                        onChange={(e) =>
                          setLimits({
                            ...limits,
                            [p.id]: [limits[p.id]?.[0] || "", e.target.value],
                          })
                        }
                      />
                    </div>
                  </div>
                ))}
              </fieldset>
              <p className="text-xs text-muted-foreground">
                Automatic limits include all finite rendered values. Unavailable
                panels remain annotated. Every observation is plotted as
                scatter, without downsampling.
              </p>
            </>
          )}
        </FieldGroup>
        <Button onClick={() => void submit()} disabled={busy}>
          {busy ? "Scheduling…" : "Generate export"}
        </Button>
      </DialogContent>
    </Dialog>
  );
}

import { useRef, useState } from "react";
import { Upload, FileCheck2 } from "lucide-react";
import { api, upload, number, type Staged, type Job } from "@/lib/api";
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
import { Progress } from "@/lib/ui/progress";
import { Alert, AlertDescription } from "@/lib/ui/alert";

export function ImportDialog({ onJob }: { onJob: (job: Job) => void }) {
  const [open, setOpen] = useState(false),
    [staged, setStaged] = useState<Staged>(),
    [busy, setBusy] = useState(false),
    [progress, setProgress] = useState(0),
    [error, setError] = useState("");
  const [station, setStation] = useState(""),
    [timestamp, setTimestamp] = useState("TIMESTAMP"),
    [mode, setMode] = useState("1min"),
    [normalize, setNormalize] = useState(true),
    [units, setUnits] = useState<Record<string, string>>({});
  const controller = useRef<AbortController | null>(null);
  const load = async (file?: File) => {
    if (!file) return;
    setError("");
    setBusy(true);
    setProgress(0);
    controller.current = new AbortController();
    try {
      const data = await upload(file, setProgress, controller.current.signal);
      setStaged(data);
      setStation(data.preview.station);
      setTimestamp(data.preview.timestamp);
      setUnits(data.preview.units);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const confirm = async () => {
    setBusy(true);
    setError("");
    try {
      const job = await api<Job>(`/imports/${staged!.id}/confirm`, {
        station,
        timestamp,
        mode,
        units,
        normalize,
      });
      onJob(job);
      setOpen(false);
      setStaged(undefined);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!busy) setOpen(value);
      }}
    >
      <DialogTrigger asChild>
        <Button>
          <Upload data-icon="inline-start" />
          Import dataset
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>
            {staged ? "Review your import" : "Import monitoring data"}
          </DialogTitle>
          <DialogDescription>
            {staged
              ? "Confirm acquisition settings before full-file validation."
              : "Upload a Campbell Scientific TOA5 or CSV text file. Up to 5 GiB by default."}
          </DialogDescription>
        </DialogHeader>
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        {!staged ? (
          <div className="upload-zone flex flex-col items-center gap-4">
            <Upload className="size-8 text-muted-foreground" />
            <p className="text-sm">
              Your original file is retained with the normalized dataset.
            </p>
            <Input
              aria-label="Dataset file"
              type="file"
              accept=".csv,.dat,.txt"
              disabled={busy}
              onChange={(e) => void load(e.target.files?.[0])}
            />
            {busy && (
              <>
                <Progress value={progress} aria-label="Upload progress" />
                <p role="status" className="text-sm">
                  {number(progress, 0)}% uploaded. Preview follows.
                </p>
                <Button
                  variant="outline"
                  onClick={() => controller.current?.abort()}
                >
                  Cancel upload
                </Button>
              </>
            )}
          </div>
        ) : (
          <div className="flex flex-col gap-5">
            <div className="flex items-center gap-3 text-sm">
              <FileCheck2 className="size-5 text-primary" />
              <span>
                {staged.name} · {staged.preview.format} ·{" "}
                {number(staged.size / 1024 / 1024)} MiB
              </span>
            </div>
            <Alert>
              <AlertDescription>
                Preview is preliminary. Every row and timestamp will be
                validated during processing. Naive timestamps are interpreted as
                UTC; aware timestamps are converted to UTC.
              </AlertDescription>
            </Alert>
            <FieldGroup className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <Field>
                <FieldLabel htmlFor="station">Station</FieldLabel>
                <Input
                  id="station"
                  value={station}
                  onChange={(e) => setStation(e.target.value)}
                  required
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="timestamp">Timestamp column</FieldLabel>
                <select
                  id="timestamp"
                  value={timestamp}
                  onChange={(e) => setTimestamp(e.target.value)}
                >
                  {staged.preview.columns.map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </Field>
              <Field>
                <FieldLabel htmlFor="mode">Acquisition mode</FieldLabel>
                <select
                  id="mode"
                  value={mode}
                  onChange={(e) => setMode(e.target.value)}
                >
                  {["1s", "2s", "1min", "6h", "zero", "span", "wx"].map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </Field>
            </FieldGroup>
            <label className="flex gap-2 items-center text-sm">
              <input
                type="checkbox"
                checked={normalize}
                onChange={(e) => setNormalize(e.target.checked)}
              />
              Normalize missing records, duplicate timestamps, and sampling gaps
            </label>
            <details>
              <summary className="text-sm font-medium">
                Channel units · confirm before calculating ratios
              </summary>
              <p className="text-xs text-muted-foreground py-3">
                Leave unknown units unconfirmed. Supported concentration units:
                ppm, ppb, %, fraction. Sulfur proportions: fraction or %.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {staged.preview.columns
                  .filter((c) => c !== timestamp)
                  .map((c) => (
                    <label className="field-label" key={c}>
                      {c}
                      <Input
                        aria-label={`Unit for ${c}`}
                        value={units[c] || ""}
                        placeholder="unconfirmed"
                        onChange={(e) =>
                          setUnits({ ...units, [c]: e.target.value })
                        }
                      />
                    </label>
                  ))}
              </div>
            </details>
            <div className="overflow-x-auto">
              <table className="data-table">
                <caption className="text-left text-xs pb-2 text-muted-foreground">
                  First {staged.preview.sample.length} records · inferred types
                  require full-file validation
                </caption>
                <thead>
                  <tr>
                    {staged.preview.columns.map((c) => (
                      <th key={c}>{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {staged.preview.sample.map((row, i) => (
                    <tr key={i}>
                      {row.map((v, j) => (
                        <td key={j}>{v}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex justify-between gap-2">
              <Button
                variant="outline"
                onClick={() => setStaged(undefined)}
                disabled={busy}
              >
                Choose another file
              </Button>
              <Button
                disabled={busy || !station.trim()}
                onClick={() => void confirm()}
              >
                {busy ? "Starting…" : "Confirm and process"}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

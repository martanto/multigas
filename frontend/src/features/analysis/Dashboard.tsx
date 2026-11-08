import { useCallback, useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ChevronLeft,
  ChevronRight,
  Database,
  FolderOpen,
  Moon,
  Sun,
  Save,
  Mountain,
  Menu,
} from "lucide-react";
import {
  api,
  fetchSeries,
  number,
  type Analysis,
  type Dataset,
  type Job,
  type Panel,
  type Stats,
  type View,
} from "@/lib/api";
import { Button } from "@/lib/ui/button";
import { Input } from "@/lib/ui/input";
import { Badge } from "@/lib/ui/badge";
import { Alert, AlertDescription } from "@/lib/ui/alert";
import { Skeleton } from "@/lib/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
  DialogHeader,
} from "@/lib/ui/dialog";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/lib/ui/table";
import { TimeChart } from "@/lib/charts/TimeChart";
import { ImportDialog } from "../import/ImportDialog";
import { ExportDialog } from "../exports/ExportDialog";
import { Coverage } from "./Coverage";
import { Filters } from "./Filters";
import { Jobs } from "./Jobs";

function readLocation(): Analysis {
  const params = new URLSearchParams(location.search);
  try {
    return JSON.parse(params.get("analysis") || "null") || { dataset: "" };
  } catch {
    return { dataset: "" };
  }
}
export function Dashboard() {
  const [plotProgress,setPlotProgress]=useState({loaded:0,total:0});
  const cache = useQueryClient(),
    [analysis, setAnalysis] = useState<Analysis>(readLocation),
    [dark, setDark] = useState(localStorage.getItem("theme") === "dark"),
    [nav, setNav] = useState(false),
    [offset, setOffset] = useState(0),
    [tab, setTab] = useState("plots"),
    [error, setError] = useState(""),
    [saveOpen, setSaveOpen] = useState(false),
    [viewName, setViewName] = useState("");
  const {
    data: datasets = [],
    isPending,
    error: datasetError,
    refetch,
  } = useQuery({
    queryKey: ["datasets"],
    queryFn: () => api<Dataset[]>("/datasets"),
  });
  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: () => api<{ panels: Panel[] }>("/health"),
  });
  const { data: views = [] } = useQuery({
    queryKey: ["views"],
    queryFn: () => api<View[]>("/views"),
  });
  const dataset = datasets.find((d) => d.id === analysis.dataset),
    panels = health?.panels || [];
  const update = useCallback((patch: Partial<Analysis>) => {
    setAnalysis((current) => ({ ...current, ...patch }));
    setOffset(0);
  }, []);
  const choose = useCallback(
    (id: string) => {
      const d = datasets.find((d) => d.id === id),
        day = d?.manifest.find((d) => d.records)?.date;
      setAnalysis({
        dataset: id,
        start: day ? `${day}T00:00:00Z` : undefined,
        end: d?.manifest.length
          ? `${d.manifest[d.manifest.length - 1].date}T23:59:59.999999Z`
          : undefined,
      });
      setOffset(0);
      setNav(false);
    },
    [datasets],
  );
  const onImported = useCallback((id: string) => {
    setAnalysis((current) =>
      current.dataset === id ? current : { dataset: id },
    );
    setOffset(0);
  }, []);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);
  useEffect(() => {
    const params = new URLSearchParams();
    params.set("analysis", JSON.stringify(analysis));
    history.replaceState(null, "", `?${params}`);
  }, [analysis]);
  useEffect(() => {
    const handler = () => setAnalysis(readLocation());
    window.addEventListener("popstate", handler);
    return () => window.removeEventListener("popstate", handler);
  }, []);
  useEffect(() => {
    if (dataset && !analysis.start && dataset.manifest.length) {
      const day = dataset.manifest.find((d) => d.records)?.date;
      if (day)
        update({
          start: `${day}T00:00:00Z`,
          end: `${dataset.manifest[dataset.manifest.length - 1].date}T23:59:59.999999Z`,
        });
    }
  }, [dataset, analysis.start, update]);
  const chartSpec = { ...analysis, channels: [] };
  const series = useQuery({
    queryKey: ["series", chartSpec],
    queryFn: ({ signal }) => fetchSeries(chartSpec, signal, (loaded,total)=>setPlotProgress({loaded,total})),
    enabled: !!dataset,
  });
  const stats = useQuery({
    queryKey: ["stats", analysis],
    queryFn: ({ signal }) => api<Stats>("/statistics", analysis, signal),
    enabled: !!dataset,
  });
  const rows = useQuery({
    queryKey: ["rows", analysis, offset],
    queryFn: ({ signal }) =>
      api<{ rows: Record<string, unknown>[]; total: number }>(
        `/rows?offset=${offset}&limit=50`,
        analysis,
        signal,
      ),
    enabled: !!dataset && tab === "rows",
  });
  const start = analysis.start?.slice(0, 10) || "",
    end = analysis.end?.slice(0, 10) || "";
  const selectDay = (day: string) =>
    update({ start: `${day}T00:00:00Z`, end: `${day}T23:59:59.999999Z` });
  const moveDay = (direction: number) => {
    const days = dataset?.manifest.filter((d) => d.records) || [];
    const next =
      direction > 0
        ? days.find((d) => d.date > end)
        : [...days].reverse().find((d) => d.date < start);
    if (next) selectDay(next.date);
  };
  const selectedDays =
      dataset?.manifest.filter((d) => d.date >= start && d.date <= end) || [],
    records = selectedDays.reduce((n, d) => n + d.records, 0),
    expected = selectedDays.reduce((n, d) => n + (d.expected || 0), 0);
  const currentPanels = (
    analysis.panels?.length ? analysis.panels : panels.map((p) => p.id)
  )
    .map((id) => panels.find((p) => p.id === id))
    .filter((p): p is Panel => !!p);
  const handleJob = (_job: Job) => {
    void cache.invalidateQueries({ queryKey: ["jobs"] });
  };
  const save = async () => {
    try {
      await api("/views", {
        name: viewName,
        analysis,
        arrangement: currentPanels.map((p) => p.id),
      });
      void cache.invalidateQueries({ queryKey: ["views"] });
      setSaveOpen(false);
      setViewName("");
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const queryError = series.error || stats.error || rows.error;
  const visibleColumns = [
    "TIMESTAMP",
    ...(analysis.channels?.length ? analysis.channels : dataset?.columns || []),
  ];
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[224px_minmax(0,1fr)]">
      <a
        href="#analysis"
        className="sr-only focus:not-sr-only focus:absolute bg-card p-3"
      >
        Skip to analysis
      </a>
      <aside
        className={`rail lg:min-h-screen p-5 flex-col gap-8 ${nav ? "flex" : "hidden lg:flex"}`}
      >
        <div className="flex items-center gap-3 text-lg font-semibold">
          <Activity className="size-7" />
          MultiGas
        </div>
        <div className="flex flex-col gap-3">
          <h2 className="text-xs font-semibold opacity-75">WORKSPACE</h2>
          <div className="nav-item">
            <Mountain className="size-4" />
            Station datasets
          </div>
          {datasets.length === 0 && (
            <p className="text-sm opacity-75 px-3">No stations imported yet</p>
          )}
          {datasets.map((d) => (
            <button
              className="nav-item flex-col !items-start"
              key={d.id}
              aria-current={d.id === analysis.dataset}
              onClick={() => choose(d.id)}
            >
              <span className="flex items-center gap-2">
                <Database className="size-4" />
                {d.station}
              </span>
              <span className="text-xs opacity-70 truncate max-w-full">
                {d.source}
              </span>
            </button>
          ))}
        </div>
        <div className="flex flex-col gap-3">
          <h2 className="text-xs font-semibold opacity-75">SAVED ANALYSES</h2>
          {!views.length && (
            <p className="text-xs opacity-75 px-3">
              Save a view to return to its dates, panels, and filters.
            </p>
          )}
          {views.map((view) => (
            <button
              key={view.id}
              className="nav-item"
              onClick={() => {
                if (view.unavailable) setError(view.unavailable);
                else {
                  setAnalysis({
                    ...view.analysis,
                    panels: view.arrangement.length
                      ? view.arrangement
                      : view.analysis.panels,
                  });
                  setOffset(0);
                  setNav(false);
                }
              }}
            >
              <FolderOpen className="size-4 shrink-0" />
              <span className="truncate">
                {view.name}
                {view.unavailable ? " (unavailable)" : ""}
              </span>
            </button>
          ))}
        </div>
        <div className="mt-auto pt-8 flex flex-col gap-2 text-xs opacity-75">
          <span>Local scientific workspace</span>
          <span>Independent imports · UTC</span>
          <span>MultiGas 0.1</span>
        </div>
      </aside>
      <div className="min-w-0">
        <header className="border-b bg-card px-4 sm:px-8 py-4 flex items-center justify-between gap-3">
          <div className="flex gap-3 items-center">
            <Button
              className="lg:hidden"
              variant="ghost"
              size="icon"
              aria-label="Toggle navigation"
              aria-expanded={nav}
              onClick={() => setNav(!nav)}
            >
              <Menu />
            </Button>
            <span className="text-sm text-muted-foreground">
              <span className="hidden sm:inline">
                Workspace <span className="mx-2">/</span>
              </span>
              <span className="text-foreground">Daily analysis</span>
            </span>
          </div>
          <div className="flex gap-2 items-center">
            <Button
              variant="ghost"
              size="icon"
              aria-label={dark ? "Use light theme" : "Use dark theme"}
              onClick={() => setDark(!dark)}
            >
              {dark ? <Sun /> : <Moon />}
            </Button>
            <ImportDialog onJob={handleJob} />
          </div>
        </header>
        <main
          id="analysis"
          className="p-4 sm:p-8 flex flex-col gap-6 max-w-[1800px] mx-auto"
        >
          <div className="flex flex-wrap justify-between items-start gap-4">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">
                {dataset
                  ? `${dataset.station} · Daily analysis`
                  : "Your monitoring workspace"}
              </h1>
              <p className="text-sm text-muted-foreground mt-2">
                {dataset
                  ? `${dataset.source} · ${dataset.mode} acquisition · All times UTC`
                  : "Import monitoring data to explore daily coverage, gas channels, and ratios."}
              </p>
            </div>
            {dataset && (
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setSaveOpen(true)}>
                  <Save />
                  Save view
                </Button>
                <ExportDialog
                  analysis={analysis}
                  panels={panels}
                  onJob={handleJob}
                />
              </div>
            )}
          </div>
          {(error || datasetError) && (
            <Alert variant="destructive">
              <AlertDescription className="flex flex-col gap-3">
                {error || datasetError?.message}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setError("");
                    void refetch();
                  }}
                >
                  Dismiss and retry
                </Button>
              </AlertDescription>
            </Alert>
          )}
          <Jobs onDataset={onImported} />
          {isPending ? (
            <div
              className="flex flex-col gap-4"
              role="status"
              aria-label="Loading datasets"
            >
              <Skeleton className="h-24" />
              <Skeleton className="h-80" />
            </div>
          ) : !dataset ? (
            <section className="surface min-h-96 flex flex-col items-center justify-center text-center gap-5 p-6">
              <Database className="size-10 text-primary" />
              <h2 className="text-xl font-semibold">
                {analysis.dataset
                  ? "Dataset unavailable"
                  : "Start with a dataset"}
              </h2>
              <p className="max-w-md text-sm text-muted-foreground leading-relaxed">
                {analysis.dataset
                  ? "This saved dataset is unavailable. Choose a station dataset or import its original file again."
                  : "Preview a CSV or TOA5 file, confirm its station and units, then explore it by day. Originals and analysis views stay on this computer."}
              </p>
              <ImportDialog onJob={handleJob} />
              <div className="text-xs text-muted-foreground">
                CSV / TOA5 · Up to 5 GiB · No automatic file merging
              </div>
            </section>
          ) : (
            <>
              <div className="surface grid grid-cols-2 xl:grid-cols-4 divide-x">
                <div className="p-4">
                  <p className="text-xs text-muted-foreground">
                    Record coverage
                  </p>
                  <p className="metric mt-2">
                    {expected
                      ? `${number(Math.min(100, (records / expected) * 100), 1)}%`
                      : "Not defined"}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Before analysis filters
                  </p>
                </div>
                <div className="p-4">
                  <p className="text-xs text-muted-foreground">
                    Records in range
                  </p>
                  <p className="metric mt-2">{number(records, 0)}</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {selectedDays.length} UTC days
                  </p>
                </div>
                <div className="p-4">
                  <p className="text-xs text-muted-foreground">
                    Filtered samples
                  </p>
                  <p className="metric mt-2">
                    {number(stats.data?.filtered_records, 0)}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {analysis.filters?.length || 0} active filters
                  </p>
                </div>
                <div className="p-4">
                  <p className="text-xs text-muted-foreground">
                    Available channels
                  </p>
                  <p className="metric mt-2">
                    {dataset.numeric_columns.length}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Validity shown per channel
                  </p>
                </div>
              </div>
              <div className="grid grid-cols-1 xl:grid-cols-[284px_minmax(0,1fr)] gap-6 items-start">
                <div className="flex flex-col gap-5">
                  <Coverage
                    key={dataset.id + start.slice(0, 7)}
                    dataset={dataset}
                    start={start}
                    end={end}
                    onSelect={selectDay}
                  />
                  <details className="surface p-4 text-xs leading-relaxed">
                    <summary className="font-semibold text-sm">
                      Dataset provenance
                    </summary>
                    <dl className="flex flex-col gap-3 mt-4">
                      <div>
                        <dt className="text-muted-foreground">
                          Dataset identifier
                        </dt>
                        <dd className="break-all">{dataset.id}</dd>
                      </div>
                      <div>
                        <dt className="text-muted-foreground">Imported</dt>
                        <dd>{dataset.created}</dd>
                      </div>
                      <div>
                        <dt className="text-muted-foreground">
                          Source SHA-256
                        </dt>
                        <dd className="break-all">{dataset.checksum}</dd>
                      </div>
                      {Object.entries(dataset.normalization).map(([k, v]) => (
                        <div key={k}>
                          <dt className="text-muted-foreground">
                            {k.replaceAll("_", " ")}
                          </dt>
                          <dd>{String(v)}</dd>
                        </div>
                      ))}
                    </dl>
                  </details>
                  <p className="text-xs leading-relaxed text-muted-foreground">
                    H₂S is uncorrected for SO₂ cross-sensitivity. H₂S ratios and
                    sulfur proportions inherit this limitation.
                  </p>
                </div>
                <div className="min-w-0 flex flex-col gap-5">
                  <div className="surface p-4 flex flex-wrap items-end gap-3">
                    <label className="field-label flex-1">
                      From (UTC)
                      <Input
                        type="date"
                        aria-label="Range start"
                        value={start}
                        onChange={(e) =>
                          update({ start: `${e.target.value}T00:00:00Z` })
                        }
                      />
                    </label>
                    <label className="field-label flex-1">
                      Through (UTC)
                      <Input
                        type="date"
                        aria-label="Range end"
                        value={end}
                        onChange={(e) =>
                          update({ end: `${e.target.value}T23:59:59.999999Z` })
                        }
                      />
                    </label>
                    <div className="flex gap-1">
                      <Button
                        variant="outline"
                        size="icon"
                        aria-label="Previous available day"
                        disabled={
                          !dataset.manifest.some(
                            (d) => d.records && d.date < start,
                          )
                        }
                        onClick={() => moveDay(-1)}
                      >
                        <ChevronLeft />
                      </Button>
                      <Button
                        variant="outline"
                        size="icon"
                        aria-label="Next available day"
                        disabled={
                          !dataset.manifest.some(
                            (d) => d.records && d.date > end,
                          )
                        }
                        onClick={() => moveDay(1)}
                      >
                        <ChevronRight />
                      </Button>
                    </div>
                  </div>
                  <Filters
                    analysis={analysis}
                    dataset={dataset}
                    panels={panels}
                    onChange={update}
                  />
                  {queryError && (
                    <Alert variant="destructive">
                      <AlertDescription>
                        {queryError.message}
                        <Button
                          variant="outline"
                          size="sm"
                          className="mt-3"
                          onClick={() => {
                            void series.refetch();
                            void stats.refetch();
                            void rows.refetch();
                          }}
                        >
                          Retry analysis
                        </Button>
                      </AlertDescription>
                    </Alert>
                  )}
                  <div className="surface overflow-hidden">
                    <div className="flex flex-wrap items-center justify-between gap-3 p-4 border-b">
                      <nav
                        aria-label="Analysis results"
                        className="flex flex-wrap gap-2"
                      >
                        {["plots", "statistics", "rows"].map((t) => (
                          <Button
                            key={t}
                            variant={tab === t ? "secondary" : "ghost"}
                            size="sm"
                            aria-pressed={tab === t}
                            onClick={() => setTab(t)}
                          >
                            {t === "plots"
                              ? "Gas & ratios"
                              : t === "rows"
                                ? "Data table"
                                : "Channel validity"}
                          </Button>
                        ))}
                      </nav>
                      <Badge variant="outline">
                        {analysis.ratio_source === "calculated"
                          ? "Calculated ratios"
                          : "Onboard ratios"}
                      </Badge>
                    </div>
                    {tab === "plots" ? (
                      series.isPending ? (
                        <div
                          className="p-5 flex flex-col gap-4"
                          role="status"
                          aria-label="Loading observations"
                        >
                          <p className="text-sm text-muted-foreground">Loading every observation{plotProgress.total?`: ${number(plotProgress.loaded,0)} of ${number(plotProgress.total,0)}`:'…'}. Select a day to inspect a smaller range.</p>
                          <Skeleton className="h-40" />
                          <Skeleton className="h-40" />
                        </div>
                      ) : (
                        <>
                          {stats.data?.filtered_records === 0 && (
                            <p
                              className="p-8 text-sm text-muted-foreground"
                              role="status"
                            >
                              No observations in this range. Choose another day
                              or adjust the filters.
                            </p>
                          )}
                          {currentPanels.map((p) => (
                            <TimeChart
                              key={p.id}
                              panel={p}
                              series={series.data || []}
                              dark={dark}
                              start={analysis.start}
                              end={analysis.end}
                              units={dataset.units}
                            />
                          ))}
                          <p className="px-5 py-4 text-xs text-muted-foreground border-t">
                            Scroll over a chart to zoom linked time axes. Hover
                            to inspect values. Every observation in the selected
                            range is plotted as scatter.
                          </p>
                        </>
                      )
                    ) : tab === "statistics" ? (
                      <div className="overflow-x-auto">
                        <Table className="data-table">
                          <caption className="text-left p-4 text-xs text-muted-foreground">
                            Full-resolution statistics after filters. Validity
                            counts finite channel observations.
                          </caption>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Channel / source</TableHead>
                              <TableHead>Valid</TableHead>
                              <TableHead>Validity</TableHead>
                              <TableHead>Minimum</TableHead>
                              <TableHead>Mean</TableHead>
                              <TableHead>Maximum</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {Object.entries(stats.data?.channels || {}).map(
                              ([c, s]) => (
                                <TableRow key={c}>
                                  <TableCell>
                                    {c}
                                    <div className="text-xs text-muted-foreground">
                                      {stats.data?.provenance[c]?.source ||
                                        "source"}{" "}
                                      ·{" "}
                                      {stats.data?.provenance[c]?.unit ||
                                        dataset.units[c] ||
                                        "unit unconfirmed"}
                                    </div>
                                  </TableCell>
                                  <TableCell>{number(s.valid, 0)}</TableCell>
                                  <TableCell>
                                    {number(s.validity, 1)}%
                                  </TableCell>
                                  <TableCell>{number(s.min)}</TableCell>
                                  <TableCell>{number(s.mean)}</TableCell>
                                  <TableCell>{number(s.max)}</TableCell>
                                </TableRow>
                              ),
                            )}
                          </TableBody>
                        </Table>
                      </div>
                    ) : (
                      <>
                        <div className="overflow-x-auto">
                          <Table className="data-table">
                            <TableHeader>
                              <TableRow>
                                {visibleColumns.map((c) => (
                                  <TableHead key={c}>{c}</TableHead>
                                ))}
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {rows.data?.rows.map((row, i) => (
                                <TableRow key={i}>
                                  {visibleColumns.map((c) => (
                                    <TableCell key={c}>
                                      {typeof row[c] === "number"
                                        ? number(row[c] as number)
                                        : String(row[c] ?? "—")}
                                    </TableCell>
                                  ))}
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                          {!rows.data?.rows.length && (
                            <p className="p-6 text-sm text-muted-foreground">
                              {rows.isPending
                                ? "Loading rows…"
                                : "No rows in this range."}
                            </p>
                          )}
                        </div>
                        <div className="p-4 flex items-center justify-between gap-2 text-xs text-muted-foreground">
                          <span>
                            {number(offset + 1, 0)}–
                            {number(
                              Math.min(offset + 50, rows.data?.total || 0),
                              0,
                            )}{" "}
                            of {number(rows.data?.total, 0)}
                          </span>
                          <div className="flex gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={!offset}
                              onClick={() =>
                                setOffset(Math.max(0, offset - 50))
                              }
                            >
                              Previous
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={offset + 50 >= (rows.data?.total || 0)}
                              onClick={() => setOffset(offset + 50)}
                            >
                              Next
                            </Button>
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              </div>
            </>
          )}
        </main>
      </div>
      <Dialog open={saveOpen} onOpenChange={setSaveOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Save analysis view</DialogTitle>
            <DialogDescription>
              Keep this dataset, UTC range, channels, filters, ratio source, and
              panel order.
            </DialogDescription>
          </DialogHeader>
          <label className="field-label">
            View name
            <Input
              autoFocus
              value={viewName}
              onChange={(e) => setViewName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && viewName.trim()) void save();
              }}
            />
          </label>
          <Button disabled={!viewName.trim()} onClick={() => void save()}>
            Save analysis
          </Button>
        </DialogContent>
      </Dialog>
    </div>
  );
}

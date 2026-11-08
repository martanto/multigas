import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { Dataset } from "@/lib/api";
import { number } from "@/lib/api";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardFooter,
} from "@/lib/ui/card";
import { Button } from "@/lib/ui/button";

export function Coverage({
  dataset,
  start,
  end,
  onSelect,
}: {
  dataset: Dataset;
  start: string;
  end: string;
  onSelect: (day: string) => void;
}) {
  const [month, setMonth] = useState(
    (start || dataset.manifest[0]?.date || new Date().toISOString()).slice(
      0,
      7,
    ),
  );
  const date = new Date(`${month}-01T00:00:00Z`),
    days = new Date(date.getUTCFullYear(), date.getUTCMonth() + 1, 0).getDate(),
    offset = (date.getUTCDay() + 6) % 7;
  const change = (delta: number) => {
    const d = new Date(`${month}-01T00:00:00Z`);
    d.setUTCMonth(d.getUTCMonth() + delta);
    setMonth(d.toISOString().slice(0, 7));
  };
  const byDay = new Map(dataset.manifest.map((d) => [d.date, d]));
  return (
    <Card className="gap-4 py-4">
      <CardHeader className="px-4">
        <div className="flex items-center justify-between">
          <CardTitle>
            <h2 className="section-title">Daily coverage</h2>
          </CardTitle>
          <span className="text-xs text-muted-foreground">UTC</span>
        </div>
      </CardHeader>
      <CardContent className="px-4 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Previous month"
            onClick={() => change(-1)}
          >
            <ChevronLeft />
          </Button>
          <span className="text-sm font-medium">
            {date.toLocaleDateString("en", {
              month: "long",
              year: "numeric",
              timeZone: "UTC",
            })}
          </span>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Next month"
            onClick={() => change(1)}
          >
            <ChevronRight />
          </Button>
        </div>
        <div className="calendar">
          {["M", "T", "W", "T", "F", "S", "S"].map((d, i) => (
            <span
              key={i}
              className="text-center text-xs text-muted-foreground py-1"
            >
              {d}
            </span>
          ))}
          {Array.from({ length: offset }, (_, i) => (
            <span key={`offset${i}`} />
          ))}
          {Array.from({ length: days }, (_, i) => {
            const day = `${month}-${String(i + 1).padStart(2, "0")}`,
              entry = byDay.get(day);
            return (
              <button
                key={day}
                data-selected={day >= start && day <= end}
                data-coverage={entry?.records ? "full" : "empty"}
                aria-label={`${day}: ${i + 1} ${entry?.completeness == null ? (entry?.records ? "n/a" : "—") : `${number(entry.completeness, 0)}%`}, ${entry?.records || 0} records`}
                aria-pressed={day >= start && day <= end}
                onClick={() => onSelect(day)}
              >
                {i + 1}{" "}
                <span>
                  {entry?.completeness == null
                    ? entry?.records
                      ? "n/a"
                      : "—"
                    : `${number(entry.completeness, 0)}%`}
                </span>
              </button>
            );
          })}
        </div>
        <p className="text-xs leading-relaxed text-muted-foreground">
          Record coverage is calculated before analysis filters. Channel
          validity is reported separately.
        </p>
      </CardContent>
      <CardFooter className="px-4 flex items-center gap-2 text-xs">
        <span className="size-3 rounded-sm bg-primary" />
        Selected
        <span className="size-3 rounded-sm bg-secondary border ml-2" />
        Data available
      </CardFooter>
    </Card>
  );
}

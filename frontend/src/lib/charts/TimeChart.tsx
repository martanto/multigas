import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { ScatterChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  TitleComponent,
  LegendComponent,
  AriaComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { Panel, Series } from "../api";
echarts.use([
  ScatterChart,
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  TitleComponent,
  LegendComponent,
  AriaComponent,
  CanvasRenderer,
]);
export function TimeChart({
  panel,
  series,
  dark,
  start,
  end,
  units,
}: {
  panel: Panel;
  series: Series[];
  dark: boolean;
  start?: string | null;
  end?: string | null;
  units: Record<string, string>;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const chart = echarts.init(ref.current!);
    chart.group = "multigas-analysis";
    const color = dark ? "#acbfb4" : "#596d65";
    const available = series.filter((s) => panel.columns.includes(s.channel));
    const compact = ref.current!.clientWidth < 400;
    const multiDay =
      !!start && !!end && Date.parse(end) - Date.parse(start) > 86400000;
    chart.setOption({
      animation: false,
      aria: {
        enabled: true,
        label: { description: `${panel.label} over time in UTC` },
      },
      grid: { left: 56, right: 24, top: 16, bottom: multiDay ? 52 : 42 },
      tooltip: { trigger: "axis" },
      axisPointer: { link: [{ xAxisIndex: "all" }] },
      xAxis: {
        type: "time",
        min: start ? Date.parse(start) : undefined,
        max: end ? Date.parse(end) : undefined,
        splitNumber: compact ? 3 : 6,
        axisLabel: {
          color,
          hideOverlap: true,
          formatter: (value: number) => {
            const utc = new Date(value).toISOString();
            return multiDay
              ? `${utc.slice(5, 10)}\n${utc.slice(11, 16)}`
              : utc.slice(11, 16);
          },
        },
        splitLine: { show: false },
      },
      yAxis: {
        type: "value",
        scale: true,
        axisLabel: { color },
        splitLine: { lineStyle: { color: dark ? "#34453c" : "#e8eee9" } },
      },
      dataZoom: [{ type: "inside", filterMode: "none" }],
      series: available.map((s, i) => ({
        name: s.channel,
        type: "scatter",
        large: true,
        largeThreshold: 10000,
        progressive: 5000,
        showSymbol: true,
        symbolSize: 2,
        itemStyle: {
          color: dark
            ? echarts.color.lift(panel.colors[i % panel.colors.length], 0.45)
            : panel.colors[i % panel.colors.length],
          opacity: dark ? 0.9 : 0.65,
        },
        dimensions: ["timestamp", "value"],
        encode: { x: 0, y: 1 },
        data: s.points,
      })),
      textStyle: { fontFamily: "Segoe UI" },
      useUTC: true,
    });
    echarts.connect("multigas-analysis");
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(ref.current!);
    return () => {
      observer.disconnect();
      chart.dispose();
    };
  }, [panel, series, dark, start, end]);
  const available = series.filter((s) => panel.columns.includes(s.channel));
  const hasValues = available.some((s) => s.valid > 0);
  return (
    <section className="border-b last:border-b-0 py-4">
      <div className="flex flex-wrap items-center justify-between gap-2 px-5">
        <h3 className="font-semibold text-sm">
          {panel.label}{" "}
          <span className="text-muted-foreground font-normal">
            {panel.unit === "source"
              ? units[panel.columns[0]] || "unit unconfirmed"
              : panel.unit}
          </span>
        </h3>
        <span className="text-xs text-muted-foreground">
          {available.length
            ? `${available.reduce((n, s) => n + s.rendered, 0).toLocaleString()} rendered points`
            : "No channel"}
        </span>
      </div>
      <div
        ref={ref}
        className={hasValues ? "chart" : "hidden"}
        role="img"
        aria-label={`${panel.label} over time in UTC`}
      />
      {!hasValues && (
        <p className="py-8 px-5 text-sm text-muted-foreground">
          Column unavailable or no valid observations in this range.
        </p>
      )}
      {panel.columns.length > 1 && (
        <div className="px-5 text-xs text-muted-foreground">
          SO₂ · orange　 H₂S · violet
        </div>
      )}
    </section>
  );
}

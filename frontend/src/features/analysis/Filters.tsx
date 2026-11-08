import { Plus, X, ArrowUp } from "lucide-react";
import { Button } from "@/lib/ui/button";
import { Input } from "@/lib/ui/input";
import { Field, FieldGroup, FieldLabel } from "@/lib/ui/field";
import type { Analysis, Dataset, Panel, Rule } from "@/lib/api";
export function Filters({
  analysis,
  dataset,
  panels,
  onChange,
}: {
  analysis: Analysis;
  dataset: Dataset;
  panels: Panel[];
  onChange: (patch: Partial<Analysis>) => void;
}) {
  const filters = analysis.filters || [],
    selected = analysis.panels?.length
      ? analysis.panels
      : panels.map((p) => p.id);
  const update = (index: number, patch: Partial<Rule>) =>
    onChange({
      filters: filters.map((r, i) => (i === index ? { ...r, ...patch } : r)),
    });
  return (
    <details className="surface p-4">
      <summary className="text-sm font-semibold">
        Analysis settings{" "}
        <span className="font-normal text-muted-foreground">
          · {filters.length} filters · {analysis.ratio_source || "onboard"}{" "}
          ratios
        </span>
      </summary>
      <div className="flex flex-col gap-5 pt-5">
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="ratio-source">Ratio source</FieldLabel>
            <select
              id="ratio-source"
              value={analysis.ratio_source || "onboard"}
              onChange={(e) =>
                onChange({
                  ratio_source: e.target.value as "onboard" | "calculated",
                })
              }
            >
              <option value="onboard">Onboard regression ratios</option>
              <option value="calculated">
                Calculated from confirmed concentration units
              </option>
            </select>
            <p className="text-xs text-muted-foreground">
              Onboard ratios are preferred when available. Confirm concentration
              units before using calculated alternatives.
            </p>
          </Field>
        </FieldGroup>
        <fieldset className="flex flex-col gap-3">
          <legend className="text-sm font-medium pb-2">
            Filters · coverage remains unchanged
          </legend>
          {filters.map((rule, index) => (
            <div key={index} className="flex flex-wrap gap-2">
              <select
                className="flex-1"
                aria-label={`Filter ${index + 1} column`}
                value={rule.column}
                onChange={(e) => update(index, { column: e.target.value })}
              >
                {dataset.numeric_columns.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
              <select
                aria-label={`Filter ${index + 1} comparison`}
                value={rule.comparator}
                onChange={(e) =>
                  update(index, {
                    comparator: e.target.value as Rule["comparator"],
                  })
                }
              >
                {[">", ">=", "<", "<=", "=", "!="].map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
              <Input
                aria-label={`Filter ${index + 1} value`}
                className="w-28"
                type="number"
                value={rule.value}
                onChange={(e) =>
                  update(index, { value: Number(e.target.value) })
                }
              />
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Remove filter ${index + 1}`}
                onClick={() =>
                  onChange({ filters: filters.filter((_, i) => i !== index) })
                }
              >
                <X />
              </Button>
            </div>
          ))}
          <Button
            variant="outline"
            className="self-start"
            size="sm"
            disabled={!dataset.numeric_columns.length}
            onClick={() =>
              onChange({
                filters: [
                  ...filters,
                  {
                    column: dataset.numeric_columns[0],
                    comparator: ">",
                    value: 0,
                  },
                ],
              })
            }
          >
            <Plus />
            Add filter
          </Button>
        </fieldset>
        <fieldset>
          <legend className="text-sm font-medium pb-2">
            Visible panels · use arrows to arrange
          </legend>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2">
            {[
              ...selected,
              ...panels.map((p) => p.id).filter((id) => !selected.includes(id)),
            ].map((id, index) => {
              const panel = panels.find((p) => p.id === id);
              if (!panel) return null;
              return (
                <div
                  className="flex justify-between items-center gap-2"
                  key={id}
                >
                  <label className="text-sm flex gap-2 items-center">
                    <input
                      type="checkbox"
                      checked={selected.includes(id)}
                      onChange={() =>
                        onChange({
                          panels: selected.includes(id)
                            ? selected.filter((p) => p !== id)
                            : [...selected, id],
                        })
                      }
                    />
                    {panel.label}
                  </label>
                  {selected.includes(id) && (
                    <Button
                      size="icon"
                      variant="ghost"
                      disabled={index === 0}
                      aria-label={`Move ${panel.label} up`}
                      onClick={() => {
                        const next = [...selected];
                        [next[index - 1], next[index]] = [
                          next[index],
                          next[index - 1],
                        ];
                        onChange({ panels: next });
                      }}
                    >
                      <ArrowUp />
                    </Button>
                  )}
                </div>
              );
            })}
          </div>
        </fieldset>
        <fieldset>
          <legend className="text-sm font-medium pb-2">
            Raw channel subset for the data table and CSV (optional)
          </legend>
          <div className="flex flex-wrap gap-3">
            {dataset.numeric_columns.map((c) => (
              <label className="flex gap-2 items-center text-xs" key={c}>
                <input
                  type="checkbox"
                  checked={analysis.channels?.includes(c) || false}
                  onChange={() =>
                    onChange({
                      channels: analysis.channels?.includes(c)
                        ? analysis.channels.filter((v) => v !== c)
                        : [...(analysis.channels || []), c],
                    })
                  }
                />
                {c}
              </label>
            ))}
          </div>
        </fieldset>
      </div>
    </details>
  );
}

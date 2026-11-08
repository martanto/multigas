import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs";
import path from "node:path";

test("import, daily workflow, saved view, and reproducible exports", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.emulateMedia({ reducedMotion: "reduce" });
  const columns = [
    "TIMESTAMP",
    "RECORD",
    "Avg_CO2_lowpass",
    "Avg_SO2",
    "Avg_H2S",
    "H2O",
    "Avg_CO2_S_tot_ratio",
    "Avg_H2S_SO2_ratio",
    "Avg_CO2_SO2_ratio",
    "Avg_H2O_CO2_ratio",
    "Avg_SO2_proportion",
    "Avg_H2S_proportion",
  ];
  const rows: string[] = [columns.join(",")];
  for (const day of [1, 2, 4])
    for (let i = 0; i < 360; i++) {
      const so2 = 2 + Math.sin(i / 20),
        h2s = 0.5 + Math.cos(i / 17) * 0.1,
        co2 = 450 + Math.sin(i / 30) * 50;
      rows.push(
        [
          `2026-01-0${day}T${String(Math.floor(i / 60)).padStart(2, "0")}:${String(i % 60).padStart(2, "0")}:00Z`,
          rows.length,
          co2,
          so2,
          h2s,
          1.5,
          co2 / (so2 + h2s),
          h2s / so2,
          co2 / so2,
          33,
          so2 / (so2 + h2s),
          h2s / (so2 + h2s),
        ].join(","),
      );
    }
  const fixture = path.resolve("../tests/dashboard-fixture.csv");
  fs.writeFileSync(fixture, rows.join("\n"));
  await page.goto("/");
  await page.getByRole("button", { name: "Import dataset" }).first().click();
  await page.getByLabel("Dataset file").setInputFiles(fixture);
  await expect(
    page.getByRole("heading", { name: "Review your import" }),
  ).toBeVisible();
  await page
    .getByLabel("Station", { exact: true })
    .fill("Lokon visual fixture");
  await page
    .getByText("Channel units · confirm before calculating ratios")
    .click();
  for (const c of ["Avg_CO2_lowpass", "Avg_SO2", "Avg_H2S"])
    await page.getByLabel(`Unit for ${c}`, { exact: true }).fill("ppm");
  await page.getByLabel("Unit for H2O", { exact: true }).fill("%");
  for (const c of ["Avg_SO2_proportion", "Avg_H2S_proportion"])
    await page.getByLabel(`Unit for ${c}`, { exact: true }).fill("fraction");
  await page.getByRole("button", { name: "Confirm and process" }).click();
  await expect(
    page.getByRole("heading", {
      name: "Lokon visual fixture · Daily analysis",
    }),
  ).toBeVisible({ timeout: 30000 });
  await page.getByRole("button", { name: "2026-01-02:", exact: false }).click();
  await expect(page.getByLabel("Range start")).toHaveValue("2026-01-02");
  await page
    .getByRole("button", { name: "Next available day", exact: true })
    .click();
  await expect(page.getByLabel("Range start")).toHaveValue("2026-01-04");
  await page
    .getByRole("button", { name: "Previous available day", exact: true })
    .click();
  await page.getByLabel("Range end").fill("2026-01-04");
  await page.getByRole("button", { name: "Data table", exact: true }).click();
  await expect(page.locator("tbody tr").first()).toBeVisible();
  await page
    .getByRole("button", { name: "Channel validity", exact: true })
    .click();
  await expect(
    page.getByRole("columnheader", { name: "Validity", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Save view", exact: true }).click();
  await page.getByLabel("View name").fill("January analysis");
  await page
    .getByRole("button", { name: "Save analysis", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "January analysis", exact: false }).last(),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "January analysis", exact: false })
    .last()
    .click();
  await page.getByRole("button", { name: "Gas & ratios", exact: true }).click();
  await expect(
    page.getByRole("img", { name: "CO₂ over time in UTC", exact: true }),
  ).toBeVisible();
  for (const size of [320, 768, 1024, 1440]) {
    await page.setViewportSize({ width: size, height: 1000 });
    await page.screenshot({
      path: `../tests/dashboard-${size}.png`,
      fullPage: true,
    });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBeTruthy();
  }
  await page.getByRole("button", { name: "Use dark theme" }).click();
  await page.screenshot({
    path: "../tests/dashboard-dark.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Use light theme" }).click();
  const scan = await new AxeBuilder({ page }).analyze();
  fs.writeFileSync(
    "../tests/dashboard-accessibility.json",
    JSON.stringify(scan.violations, null, 2),
  );
  expect(scan.violations).toEqual([]);
  for (const kind of ["csv", "zip", "figure"]) {
    await page.getByRole("button", { name: "Export", exact: true }).click();
    await page.getByLabel("Export type").selectOption(kind);
    if (kind === "figure")
      await page.getByLabel("DPI", { exact: true }).fill("60");
    const [response] = await Promise.all([
      page.waitForResponse(
        (r) => r.url().endsWith("/exports") && r.request().method() === "POST",
      ),
      page.getByRole("button", { name: "Generate export" }).click(),
    ]);
    const job = await response.json();
    await expect
      .poll(
        async () => {
          const r = await request.get(`/api/v1/jobs/${job.id}`);
          return (await r.json()).status;
        },
        { timeout: 60000 },
      )
      .toBe("complete");
    const result = await (await request.get(`/api/v1/jobs/${job.id}`)).json();
    expect(
      (await request.get(`/api/v1/downloads/${result.result.artifact}`)).ok(),
    ).toBeTruthy();
  }
  await page.getByRole("button", { name: "2026-01-03:", exact: false }).click();
  await expect(
    page.getByText(
      "No observations in this range. Choose another day or adjust the filters.",
    ),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

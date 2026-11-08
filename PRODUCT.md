# MultiGas local analysis
<!-- impeccable:product-schema 1 -->

## Platform
web

## Stack
React, Vite, TypeScript, Tailwind v4, shadcn/ui, ECharts; FastAPI and DuckDB.

## Users and purpose
Volcanic gas monitoring researchers inspect persistent Campbell Scientific
datasets by UTC day, compare concentrations and ratios, and export reproducible
full-resolution data and scientific figures.

## Operating constraints
Local single-user application. Independent imports, no automatic file merging,
authentication, telemetry, or watched folders. Naive timestamps mean UTC.
Coverage describes the immutable dataset; filters describe an analysis view.
Units must be confirmed before calculating concentration ratios.

## Evidence
The implementation brief specifies a ten-panel portrait summary. Its referenced
image is not available in this session. No measured data ships as real observations.

## Accessibility
Keyboard-operable controls, responsive at 320–1440 pixels, light and dark themes.

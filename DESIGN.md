---
name: MultiGas workspace
description: A restrained scientific workspace for UTC monitoring data.
colors:
  primary: "#216653"
  primary-foreground: "#fff"
  background: "#f3f5f2"
  foreground: "#1b302c"
  card: "#fff"
  secondary: "#e4eee8"
  muted: "#edf0ed"
  muted-foreground: "#596d65"
  border: "#d9e1dc"
  destructive: "#a33531"
  rail: "#173c35"
  rail-text: "#e4eeea"
  dark-background: "#121d1a"
  dark-foreground: "#e6eee9"
  dark-card: "#1b2a25"
  dark-primary: "#87cbb0"
  dark-primary-foreground: "#142d23"
  dark-secondary: "#2a4036"
  dark-muted: "#263730"
  dark-muted-foreground: "#acbfb4"
  dark-border: "#3a4d43"
  dark-destructive: "#ffb1a7"
  dark-rail: "#102b24"
  sulfur-orange: "#b36a26"
  sulfide-violet: "#775b98"
typography:
  metric:
    fontFamily: '"Segoe UI", sans-serif'
    fontSize: "1.75rem"
    lineHeight: 1.3
    letterSpacing: "-0.025em"
  headline:
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: "2rem"
    letterSpacing: "-0.025em"
  title:
    fontSize: "1rem"
    fontWeight: 650
  body:
    fontFamily: '"Segoe UI", sans-serif'
    fontSize: "0.875rem"
    lineHeight: "1.25rem"
  label:
    fontSize: "0.75rem"
    lineHeight: "1rem"
rounded:
  sm: "0.25rem"
  md: "0.375rem"
  lg: "0.5rem"
  card: "0.75rem"
  pill: "9999px"
spacing:
  step-1: "0.25rem"
  step-2: "0.5rem"
  step-3: "0.75rem"
  step-4: "1rem"
  step-5: "1.25rem"
  step-6: "1.5rem"
  step-8: "2rem"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary-foreground}"
    rounded: "{rounded.md}"
    height: "2.25rem"
    padding: "0.5rem 1rem"
  button-outline:
    backgroundColor: "{colors.background}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.md}"
    height: "2.25rem"
  button-ghost:
    rounded: "{rounded.md}"
    height: "2.25rem"
  input:
    backgroundColor: "{colors.card}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.md}"
    height: "2.25rem"
    padding: "0.5rem 0.625rem"
  surface:
    backgroundColor: "{colors.card}"
    rounded: "{rounded.lg}"
  coverage-card:
    backgroundColor: "{colors.card}"
    rounded: "{rounded.card}"
    padding: "1rem"
  badge-secondary:
    backgroundColor: "{colors.secondary}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.pill}"
    padding: "0.125rem 0.5rem"
---

# Design System: MultiGas workspace

## Overview

**Creative North Star: "The Botanical Field Atlas"**

Forest navigation, pale paper surfaces, and quiet dividers frame dense scientific observations. The workspace prioritizes readable measurements, familiar controls, and clear selections. Its botanical character comes from its palette rather than decorative illustration.

The implementation combines custom analysis surfaces with shadcn primitives. Light and dark themes preserve semantic roles; scientific figures remain white independently of the application theme.

**Key Characteristics:**
- Forest navigation and restrained green selection.
- Compact summaries with tabular measurements.
- Bordered analysis surfaces and familiar form controls.
- UTC labels, explicit units, and textual coverage signals.

## Colors

The palette balances pale green paper with deep forest ink; orange and violet separate sulfur channels.

### Primary
- **Field Green** (`primary`): primary actions, selected calendar days, and focus. **Light Field Green** (`dark-primary`) serves the same role in dark mode.

### Secondary
- **Sulfur Orange** (`sulfur-orange`) and **Sulfide Violet** (`sulfide-violet`): SO₂ and H₂S concentration and sulfur proportion traces.
- Other scientific panel colors belong to the panel definitions in `src/multigas/utils/analysis.py`; preserve their channel mapping when reusing those panels.

### Neutral
- **Paper** (`background`), **White Surface** (`card`), and **Pale Foliage** (`secondary`, `muted`) separate workspace, containers, and subdued states.
- **Forest Ink** (`foreground`) carries text; **Quiet Ink** (`muted-foreground`) carries metadata and axes.
- **Forest Rail** (`rail`, `rail-text`) anchors navigation. Dark mode uses the corresponding `dark-*` roles; rail text remains shared.
- **Fine Rule** (`border`) separates controls, rows, and panels. **Error Red** (`destructive`) marks failures.

**The Explicit Signal Rule.** Pair coverage color with percentages, missing-value marks, accessible labels, and a selection legend.

## Typography

**Body Font:** Segoe UI, sans-serif. Chart text shares the same family. No distinct decorative display family is established.

### Hierarchy
- **Metric:** largest quantitative role; tabular numerals and close tracking stabilize comparisons.
- **Headline:** compact page heading; semibold with close tracking.
- **Title:** section headings; emphasis comes from weight rather than a large size jump.
- **Body:** controls, descriptions, and panel titles.
- **Label:** provenance, table values, UTC markers, and secondary counts. Tables use tabular numerals.

Intermediate field labels and larger dialog titles supplement this hierarchy. Tiny calendar percentages are a compact component detail, not a general text-size recommendation.

## Layout

At the large breakpoint (1024px), the shell uses a station rail (224px) and a flexible content column. Navigation becomes an explicit disclosure below that width. Main content is centered with a maximum width (1800px), padding (16px, rising to 32px at 640px), and vertical gaps (24px).

Summaries occupy two columns, rising to four at 1280px. Coverage and provenance precede charts in the single-column layout; at 1280px they occupy a side column (284px). Flexible controls wrap. Tables retain their column structure in a horizontal scroll container. Spacing follows the frontmatter's quarter-rem scale.

## Elevation & Depth

Borders and tonal surfaces provide most separation. Custom analysis surfaces are flat; shadcn inputs and outlined buttons carry an extra-small shadow, and the coverage card carries a small shadow. Dialogs use a larger soft shadow over a half-black overlay. A universal no-shadow rule would misdescribe the shipped implementation.

**The Quiet Depth Rule.** Keep data panels legible through borders and spacing; reserve pronounced depth for modal content.

## Shapes

Controls have gently curved corners, custom panels slightly wider corners, and the shadcn coverage card a larger radius. Badges are pills. Calendar cells use the smallest radius. Thin solid borders define surfaces and inputs; the import target uses a dashed border. Icons are SVG components.

## Components

### Buttons

Compact controls use primary, outline, and ghost variants. Default buttons use medium-weight body text; icons are usually 16px. Primary hover lowers background opacity to 90%; outline and ghost hover use the secondary surface. Keyboard focus uses the primary ring; disabled controls reduce opacity and stop pointer interaction.

### Chips

Small pill badges communicate statuses and counts. Secondary badges use secondary fill and foreground ink.

### Cards / Containers

Custom analysis containers use one border and the `surface` shape. Coverage uses the shadcn card shape, subdued shadow, and tighter padding than its library default. Charts are separated within a shared container by horizontal rules.

### Inputs / Fields

Fields use a thin border, semantic surface fill, rounded control corners, and visible labels. Inputs share the standard control height. Focus adds a primary border and translucent ring. Invalid fields use the destructive role; disabled fields reduce opacity. Dark shadcn inputs use translucent input fill.

### Navigation

The forest rail groups station datasets and saved analyses. Active and hovered entries use a translucent white fill; source filenames are secondary text. The mobile header exposes navigation and theme controls with accessible names.

### Coverage Calendar

Seven equal columns use compact day cells. Available days use secondary fill; the selected range uses primary fill and contrasting text. Percentages or missing-value marks remain visible. Selection focuses the analysis on one UTC day without altering immutable dataset coverage.

### Linked Scientific Panels

Scatter panels share a time cursor and inside zoom. Each plot is 190px high, with an explicit title, unit, and rendered point count. All observations are retained; the initial range spans the dataset. Missing channels retain their panel and an explanatory message. Time labels use UTC and include dates across multi-day ranges. Dark charts lighten source colors and use theme-aware axes. Reduced-motion preferences disable transitions; chart animation is already disabled.

## Do's and Don'ts

### Do:
- **Do** preserve semantic theme roles and scientific channel colors.
- **Do** keep units, UTC context, and missing-channel messages explicit.
- **Do** retain all observations and the full dataset as the initial range.
- **Do** use visible labels, SVG icons, and keyboard focus states.

### Don't:
- **Don't** use coverage color as the sole signal.
- **Don't** let analysis filters redefine immutable coverage.
- **Don't** apply application dark backgrounds to exported scientific figures.
- **Don't** treat unused eyebrow styling or system-font display headings as a new reusable visual rule.

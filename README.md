# TRUSTVISION — AI Integrity Assurance (Frontend UI)

A government-grade (Ministry of Defence style) AI assurance platform front end.
Dataset, Model and Inference assurance workflows with a clean charcoal / navy /
white enterprise theme. **Frontend only — all data is mock JSON, no backend.**

Built to match the project design documentation (Dataset / Model / Inference
assurance pages as specified).

## Tech Stack

- [React 19](https://react.dev) + [TypeScript](https://www.typescriptlang.org)
- [Vite](https://vite.dev) (build tooling)
- [TailwindCSS v4](https://tailwindcss.com) (`@tailwindcss/vite` plugin, custom navy/ink theme in `src/index.css`)
- [Recharts](https://recharts.org) (drift histograms)
- [Lucide Icons](https://lucide.dev)
- [React Router v7](https://reactrouter.com)

## Getting Started

```bash
npm install
npm run dev       # start dev server (http://localhost:5173)
```

Production build & preview:

```bash
npm run build     # type-check + bundle to dist/
npm run preview   # serve the production build (http://localhost:4173)
```

## Pages

| Route                   | Module                                                          |
| ----------------------- | --------------------------------------------------------------- |
| `/`                     | Dashboard — KPI tiles + recent assessments                       |
| `/assurance/datasets`   | Dataset Assurance — overview, quality gauges, drift tabs, contributor risk, anomaly assessment, evidence preview, trust score & actions |
| `/assurance/models`     | Model Assurance — overview, risk analysis, access mode (white/black box), training source risk, trust score & actions |
| `/assurance/inference`  | Inference Assurance — input & prediction, provenance verification (copyable hashes), integrity checks, trust report & actions |
| `/audit/reports`        | Audit & Reports — immutable action ledger table                  |

Fully responsive: the sidebar collapses into a drawer below `lg`, and all card
grids reflow from 4-column desktop layouts to 2-column and single-column stacks.

## Project Structure

```
src/
├── App.tsx                  # routes
├── index.css                # Tailwind v4 theme (navy + ink palettes)
├── types.ts                 # shared TypeScript types for the mock data
├── data/                    # mock JSON (dataset, model, inference, dashboard, audit)
├── components/
│   ├── layout/              # Sidebar, TopBar, AppLayout
│   ├── ui/                  # Card, Chip, Button, Gauge, ProgressBar
│   ├── PageHeader.tsx       # accent-bar page title + right slot
│   ├── FileCard.tsx         # "coco_dataset.zip / Upload New" header card
│   └── EvidenceThumb.tsx    # SVG scene placeholders (tank/truck/plane/snow)
└── pages/                   # one file per route
```

## Notes

- All numbers, files, contributors and hashes are mock data in `src/data/*.json`,
  typed by `src/types.ts` — swap them for API calls when a backend exists.
- Evidence "photos" are inline SVG placeholders so the app works fully offline.
- Buttons are intentionally inert (UI-only deliverable); the copy icons on the
  Inference page do write to the clipboard.

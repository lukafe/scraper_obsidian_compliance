# CertiK — Crypto Regulation Market Intelligence Dashboard

Next.js 15 + Tailwind. Reads from `../vault/_export/*.{csv,json}` at build
time and serves a Vercel-ready static dashboard.

## Local dev

```bash
cd web
npm install
npm run dev
# open http://localhost:3030
```

The `predev` and `prebuild` scripts auto-run `node scripts/prepare-data.mjs`
to refresh `public/data/*.json` from the vault export.

## Build / preview

```bash
npm run build
npm run start
```

## Pages

| Route | What it shows |
|---|---|
| `/` | Executive Summary — Money Chart (urgency × service intensity bubble), top opportunities table, aggregated service demand. |
| `/map` | Interactive world choropleth (4 metrics). |
| `/timeline` | Every regulatory deadline mapped, grouped by country, color-coded by urgency. |
| `/services` | Grid of 14 security services → drilldown to top markets per service. |
| `/jurisdictions` | Card grid of 23 countries; click for full profile. |
| `/jurisdictions/[iso]` | Full country profile: KPIs, services triggered, every norm with LLM-extracted scope and gap, connected frameworks. |
| `/methodology` | Pipeline, scoring formula, confidence policy, known limits. |

## Data refresh

When you re-run the Python pipeline and the `vault/_export/*` files update,
just `npm run build` (or `npm run dev`) again — the predev hook re-emits
`public/data/*.json`.

## Deploy to Vercel

The web app lives in `web/`, **not** at the repo root. In the Vercel project
settings, set:

- **Root Directory**: `web`
- **Framework Preset**: Next.js (auto-detected)
- **Build Command**: `npm run build` (auto)
- **Output Directory**: `.next` (auto)
- **Install Command**: `npm install` (auto)

`vercel.json` is included but Vercel auto-detects everything correctly anyway.

### One important note

Because the data files come from `../vault/_export/`, **commit
`web/public/data/*.json` to git**. They're already produced by the prebuild
script — just include them in the commit. Otherwise the Vercel build won't
find the vault export (which lives in a sibling folder not deployed with
the web app).

## Stack

- Next.js 15 (App Router, Server Components)
- TypeScript
- Tailwind CSS 3
- Recharts (bubble chart)
- react-simple-maps (choropleth)
- lucide-react (icons)
- No backend / API — fully static

# Design system — CyberAgent frontend

Every visual rule that is actually implemented, with the file it lives in.

## Where the tokens live

- `frontend/src/index.css` holds every custom token as hand-written CSS classes across 11 dense
  lines. Tailwind v4 arrives through `@tailwindcss/vite` in `vite.config.ts`, so the only other
  colours available are the default Tailwind palette.
- `frontend/tailwind.config.js` is tracked but read by nothing (no `@config` in `index.css`), so its
  `navy` palette generates no CSS. Components still write `navy-*` in 10 files, 75 occurrences; one is
  patched (`.card .bg-navy-800 { background: rgba(255,255,255,.04) }`) and the rest fall through to
  the inherited value, including the sticky confusion-matrix header
  (`components/model-results/ConfusionMatrixTable.tsx:80`).

## Colour and surfaces

| Token | Value | Use |
| --- | --- | --- |
| page background | `#0a0e27` | `:root` and `body` |
| text | `#f8fafc` | `:root` |
| `.muted` | `#94a3b8` | secondary text; `.card .text-muted-foreground` maps to the same value |
| `.eyebrow` | `#22d3ee`, `.69rem`, weight 700, `.12em`, uppercase | kicker above a section heading |
| `.app-canvas` | radial glows `rgba(102,126,234,.18)` and `rgba(34,211,238,.06)` over `#0a0e27`, plus a `::before` grid of `rgba(148,163,184,.07)` lines on `48px` cells, masked at 90% height | app shell and depth |
| `.glass` | `rgba(16,23,51,.68)`, 1px `rgba(255,255,255,.1)`, blur 18px, shadow `0 16px 48px` | filter bar, sidebar |
| `.surface` | `rgba(8,13,34,.92)`, 1px `rgba(255,255,255,.09)`, shadow `0 14px 35px` | panels holding tables |
| `.panel` / `.card` | radius `20px`; `.card` adds `padding: 1.25rem` | used with `.glass` or `.surface` |
| `.btn` | radius `10px`, `rgba(255,255,255,.05)` fill, `rgba(255,255,255,.12)` border, `#cbd5e1` text | secondary action; hover moves the border to `rgba(34,211,238,.55)` |

## Typography

`Satoshi` is named in `:root` and `Clash Grotesk` in `.font-display`, but `index.html` loads no webfont
and there is no `@font-face`, so the real body face is `ui-sans-serif`. `.mono` carries flow IDs, IPs,
timestamps and numeric cells. Headings are `font-display text-3xl font-semibold`, table body text is
`.82rem`, table headers `.68rem` uppercase with `.08em` tracking.

## Badges and honest labelling

`.badge` is a pill with a leading dot (`::before`, `.4rem`, `currentColor`). The variants only set
foreground, a `.11` background tint and a `.24` border: `badge-emerald` `#34d399`, `badge-cyan`
`#22d3ee`, `badge-amber` `#fbbf24`, `badge-red` `#f87171`.

Amber means "not live" and is mandatory on anything that is a fixture, demo data or a simulation:
"Demo data" and "Simulated" (`AlertsDashboard.tsx:17,19`), "Demo fixtures" (`ReplayView.tsx:19`),
"Fixture-backed overview" (`pages/Overview.tsx:29`), "Simulated — not live traffic"
(`pages/Simulation.tsx:112`, `WarGameReplay.tsx:121`), "Held-out evaluation, not operational traffic"
(`ModelResultsPage.tsx:52`).

Alert severity maps `critical|high → badge-red`, `medium → badge-amber`, `low → badge-emerald`
(`AlertsDashboard.tsx:14`). Simulation host states each get a border, a text colour and a label
(`WarGameReplay.tsx:20-37`): clean blue-400, scanned amber-400, compromised red-500 with a
`shadow-[0_0_18px_rgba(248,113,113,0.5)]` glow, isolated dashed slate-400, shielded emerald-400.

Class colours come from one map in `lib/classLabels.ts:70-88`: BENIGN `#38bdf8`, Bot `#f87171`, DDoS
`#fb923c`, DoS GoldenEye `#facc15`, DoS Hulk `#ef4444`, DoS Slowhttptest `#a3e635`, DoS slowloris
`#4ade80`, FTP-Patator `#22d3ee`, PortScan `#818cf8`, SSH-Patator `#e879f9`, Web Attack `#f472b6`,
`#94a3b8` when unknown. `ClassLabel` prints that colour and, for a label the model cannot emit, appends
an amber note chip (`bg-amber-400/15`) instead of renaming it.

## Numbers

`lib/format.ts` is the only formatter for confidences and percentages: two decimals, and any value
below 1 is capped so it can never print `100.00%`. Integers use `toLocaleString('en-US')`, seconds two
decimals, milliseconds one, timestamps render as `YYYY-MM-DD HH:MM:SS UTC`. A flow field missing from
the stored record says "not in the record"; a run with no record says "no flow record attached to this
run" (`InvestigationView.tsx:86-93`). The SHAP bar label is the deliberate exception: `signedLabel`
keeps three decimals for effect magnitudes and emits an em dash for missing data
(`InvestigationView.tsx:26-28`).

## Tables and charts

`.data-table` is `border-collapse` with `.85rem 1rem` cells, `1px` row separators at
`rgba(255,255,255,.07)` and a `rgba(34,211,238,.035)` row hover. The confusion matrix toggles between
counts (a `0` dimmed to `text-slate-600`) and row-normalised values at one decimal, and shows a
consistency pill from the same artifact (`ConfusionMatrixTable.tsx:31,34-35,67-75`). That pill and
`components/ui/badge.tsx` both use light Tailwind pairs (`bg-emerald-100 text-emerald-800`,
`bg-red-100 text-red-800`), which read as light chips on the dark canvas: a third badge style next to
the tinted `.badge` pills.
Recharts curves use `type="stepAfter"` so a drawn value is always a measured point,
`isAnimationActive={false}`, grid `#334155`, axes `#64748b`, tooltip `#0f172a` on a `#334155` border.

## Empty and error states

`/model-results` stays empty on purpose when the artifact is missing and prints the two commands that
would fill it (`ModelResultsPage.tsx:10-32`). Replay controls render disabled as "Start unavailable",
with a title saying they are not wired to a backend (`ReplayView.tsx:139`).

## Accessibility that exists

`:focus-visible` paints a `2px #22d3ee` outline at `3px` offset on buttons, links, inputs and selects.
The alerts search box and severity select carry `aria-label`s. War-game replay takes space for
play/pause and arrows for stepping, watches `prefers-reduced-motion` (`WarGameReplay.tsx:46-52`), and
the `.lift` hover only applies under `prefers-reduced-motion: no-preference`. Below `760px` the desktop
sidebar is hidden.

## Known inconsistencies

1. Two badge systems: the CSS `.badge` pill and `components/ui/badge.tsx`, whose variants emit
   `bg-navy-*` (no CSS) or a light `bg-red-100 text-red-800`.
2. `components/shared/SeverityBadge.tsx` is imported nowhere.
3. `tailwind.config.js` is wired to nothing; use it with `@config` or delete it.

# Collections Page — Redesign Proposal

**Status:** Draft for review
**Date:** 2026-04-28
**Scope:** `medialake_user_interface/src/pages/CollectionsPage.tsx` and shared components
**Baseline screenshots:** `artifacts/design/current-collections-page.png`, `artifacts/design/current-search-page.png`

---

## Why

The current Collections page uses a toolbar that looks and behaves differently from the Search page even though both show grids of result cards with pagination, sort, and filter. The toolbar mixes three different control styles in a single row (MUI `Select` combobox for sort field, toggle-button group for direction, another `Select` for metadata filter, plus a bare `TextField` for search), and the action overlay on cards is hidden until hover — which is invisible on touch and hard to discover on desktop.

Two specific issues:

1. **Inconsistent with Search.** Search uses a unified "Sort / Fields / Appearance" button group (`AssetViewControls`) where each trigger opens a compact popover with listbox-style options, active-value chips, and a directionless toggle baked into the selected row. Collections does not use this pattern and therefore feels like a different product.
2. **Custom metadata is sortable nowhere.** Collections support arbitrary `customMetadata` key/values but the UI only exposes three sort fields (name, createdAt, updatedAt). Users who tag collections with a "priority", "campaign", or "budget" metadata key have no way to sort the grid on it. The Search page already solves this with its "Sort by" popover that splits "Standard fields" and "Custom metadata" sections.

This redesign aligns Collections with the Search page's control pattern, adds custom-metadata sort, and gives the card grid a cleaner information hierarchy that reads the same in both light and dark modes.

---

## Aesthetic direction

Operator console, not marketing site. The existing app is a productivity tool for media teams who spend hours inside it. The redesign leans into that: calm surfaces, high-contrast type, decisive accent color, zero chrome.

- **Type**: keep the app's body font (Noto Sans / system stack already in use) for consistency. Use a monospaced token (`ui-monospace, "SF Mono", "JetBrains Mono", ...`) for result counts and metadata values so numeric data reads cleanly.
- **Color**: reuse the existing MUI theme primary/secondary tokens. Add one new semantic token: `surface.elevated` (`alpha(text.primary, 0.02)` light / `alpha(common.white, 0.04)` dark) for the toolbar strip so it separates from the card grid without a heavy border.
- **Motion**: 120ms ease transitions only, used on popover open, active-state color changes, and the card hover lift. No page-load staggered reveals — it's a data tool, not a landing page.
- **Density**: 16px vertical rhythm. Card thumbnail 160px (down from 180px) to let 5 cards fit on a standard 1440px laptop without scrolling past the fold.

---

## Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Collections                                                  [+ Create]     │  ← header
│  Organize and manage your media assets in collections                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  [All] [Mine] [Shared with me] [Shared by me] [Groups]                       │  ← filter tabs
├─────────────────────────────────────────────────────────────────────────────┤
│  🔍 Search collections…        │  ⌵ Sort: Name ↑  │ ⚙ Filters (0)  │ ⊞ ⊟    │  ← toolbar strip
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  [card]  [card]  [card]  [card]  [card]                                     │
│  [card]  [card]  [card]  [card]  [card]                                     │
│                                                                              │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  Showing 1 – 100 of 2,020                                 ‹ 1 2 3 … 21 ›    │  ← pagination
└─────────────────────────────────────────────────────────────────────────────┘
```

Four horizontal bands, each doing one job:

1. **Page header** — title + primary CTA. Untouched.
2. **Filter tabs** — the existing tab row. Keep as-is; it already matches the app's voice.
3. **Toolbar strip** — replaces the current mixed-control row. Uses the `AssetViewControls` trigger-button style (search, sort, filters, view). Sits on the new `surface.elevated` background so it visually reads as a single strip.
4. **Card grid** — same responsive grid but with simplified cards.
5. **Pagination** — unchanged row; just moves into a subtle top border instead of the current stack layout.

---

## Toolbar — detailed

All triggers are MUI `Button`s using the shared `triggerButtonSx` helper from `AssetViewControls`, so active state, focus ring, and popover anchoring match the Search page exactly.

### Search input

- `InputBase` with leading search icon, 320px wide, 36px tall.
- Clears with an X chip on the right when populated.
- Debounces at 300ms (unchanged).

### Sort button

- Label: "Sort: {activeLabel} ↑/↓" when active, just "Sort" when default.
- Icon: `SortIcon` leading, `KeyboardArrowDownIcon` trailing.
- Click opens a 280px popover with:
  - **Header row**: "Sort by" label + a "Clear" icon button (only shown when not at default).
  - **Standard fields section** — listbox with three items: Name, Date created, Date updated. Active row shows a check mark and an "Asc/Desc" chip that also acts as the direction toggle (click the chip to flip direction without leaving the popover; click anywhere else on the row to pick a different field, which uses direction `asc` by default for strings and `desc` for dates).
  - **Custom metadata section** (only shown when `metadataKeys.length > 0`) — divider + uppercase "Custom metadata" overline label + one listbox item per key (`customMetadata.priority`, `customMetadata.campaign`, etc.). Rows behave identically to the standard section.
- Matches the Search page sort popover 1:1 visually.

### Filters button

- Opens a popover containing the **metadata key/value filter** that's currently on the toolbar. Moving it into a popover declutters the main row and matches how Search handles its field-level filters.
- Trigger shows a small badge with the count of active filters.

### View toggle

- Two-button toggle: grid (default) / list. Small tertiary control; rightmost on the strip.
- List view is a new affordance — same data, rendered as a dense table-like row with thumbnail thumbnail, name, owner, updated date, and active sort field as a right-aligned column. Useful for power users who manage hundreds of collections.

### Active-state pills row (below the strip, shown only when filters/sort are active)

- "Sort: Name ↑ ×" and "Campaign = Q1 ×" chips that remove the respective filter when dismissed. Gives feedback without reopening popovers. Same pattern search already has.

---

## Card — detailed

Current card has three issues: the action overlay only appears on hover, the "0 assets · 10 sub · Apr 27, 2026" metadata row is dense and hard to scan, and the `Public` badge is buried at the bottom.

New card:

```
┌──────────────────────────────────┐
│ ┌────────────────────────────┐   │
│ │                            │   │
│ │       [thumbnail]          │   │
│ │                         🌐 │   │  ← visibility badge, top-right
│ │                            │   │
│ └────────────────────────────┘   │
│                                   │
│  Accessibility           ⋯       │  ← name + action menu
│  Department · all projects       │
│  ─────────────────────────────    │
│  10 sub · 0 assets   Apr 27       │
└──────────────────────────────────┘
```

Changes:

- **Thumbnail 160×160**, rounded 12px. Placeholder uses the collection-type accent color (existing behavior) at 10% opacity.
- **Visibility badge** as a small icon pill in the top-right of the thumbnail. Three states: 🌐 Public, 👥 Shared, 🔒 Private. Always visible (was hidden before).
- **Name** in body-strong 14px, truncates at one line.
- **Description** (new) in body-small 12px `text.secondary`, truncates at one line. Falls back to the collection type name when no description exists.
- **Action menu** replaces the hover-only action buttons. Single `⋯` icon button opens a small menu with Share / Edit / Delete. Always visible, always keyboard-accessible, still gated by `userRole` and `useActionPermission`. Faster to find, works on touch.
- **Meta row** at the bottom of the card: two monospaced tokens (`10 sub · 0 assets`) on the left, `Apr 27` on the right. Separated by a hairline divider for visual rhythm.
- **Hover** raises the card 2px with a shadow bump (unchanged intent, just lighter). No border-color shift (was heavy in the current design).
- **When a custom-metadata sort is active**, the active key/value shows as a small chip above the meta row, so the reason the card is in its current position is visible at a glance.

---

## Custom metadata sort — how it flows end-to-end

1. The Sort popover lists metadata keys from `useGetMetadataKeys()` under a "Custom metadata" section.
2. When the user picks `customMetadata.priority`, `CollectionsPage` calls `useGetCollections({ sort: "customMetadata.priority", sortDirection: "asc", ... })`.
3. The FE passes it through unchanged as `sort=customMetadata.priority` on the query string.
4. The Pydantic `ListCollectionsQueryParams.sort` field currently restricts the pattern to `^(name|createdAt|updatedAt)$`. Extend it to `^(name|createdAt|updatedAt|customMetadata\.[A-Za-z0-9_-]+)$` with an additional validator that rejects keys with dots beyond the one segment (same regex used for metadata filter keys).
5. `search_collections(sort_field=...)` already accepts a generic `sort_field`. Update the `sort_key` derivation so `customMetadata.X` maps to `customMetadata.X.keyword` (the mapping already has `.keyword` subfields on all customMetadata values — that was added for filtering).
6. Because `customMetadata` values are indexed as `keyword`, sort works on any string. For numeric metadata users will sort lexicographically (e.g. `"100" < "20"`). That's acceptable for v1; we can add numeric detection later if it matters.
7. Nothing else in the backend changes. No migration, no re-index.

---

## List view (new)

Toggleable from the toolbar, serves power users managing many collections.

```
Thumbnail  Name                 Owner            Updated       Items    Sort value
─────────────────────────────────────────────────────────────────────────────────
[▢]        Accessibility        Me               Apr 27        10 sub   —
[▢]        Animation            Jane Smith       Apr 27        10 sub   —
[▢]        Archive              Me               Apr 27        10 sub   —
```

Uses `AssetTable` under the hood (already in the codebase, same component the Search page uses for table view). Columns: name, owner name, updated date, item count, and — when a custom-metadata sort is active — the value of that metadata key for each row.

Deferred to v1.1. Not part of the first PR unless the user explicitly asks for it in the review. The first PR will land the toolbar + card refresh + custom-metadata sort.

---

## What's in v1 vs later

**v1 (this PR):**

- Toolbar strip: search + sort popover + filters popover + (grid/list) view toggle stub
- Sort popover with Standard + Custom metadata sections
- Backend: extend `sort` validator and sort-key mapping
- Card: always-visible actions menu, visibility badge, description line, meta row with divider, chip for active custom-metadata sort
- Active-state chips row under the toolbar
- i18n strings for all new labels in `en.ts`

**v1.1 (deferred):**

- List view implementation (renders with `AssetTable`)
- Numeric-aware sort for metadata keys with numeric values (detect at query time)
- Saved views (remember last sort + filters per user)

---

## Open questions for review

1. **Does the "mixed permissions" card menu (⋯) replace the current hover buttons completely, or keep the hover buttons as a secondary affordance?** Proposal: replace. Hover-only controls are a discoverability antipattern.
2. **Should the Sort button label show full text ("Sort: Name ↑") or just the icon when the active sort is default?** Proposal: just "Sort" when at default, full label when active — same as Search.
3. **Acceptable to add one new shared component `CollectionViewControls` that wraps `AssetViewControls` with collection-specific sort defaults, or should we inline the pattern in `CollectionsPage`?** Proposal: new wrapper. It's a straight reuse and makes the sort-options list type-safe.

---

## Preview

A self-contained HTML/CSS prototype showing the proposed layout lives next to this file at `artifacts/design/collections-redesign-preview.html`. Open it in a browser to see the exact card, toolbar, and sort popover visual direction before any React code is touched.

---

# Addendum v2 — Tags, Collection Detail View, and Thumbnail Consistency

> **Added:** 2026-04-28 (round 2)
> **Trigger:** Reviewer asked how tags appear on cards, how metadata and tags are laid out on the collection detail page, and for the thumbnail aspect ratio to be consistent everywhere.
> **Baseline screenshot:** `artifacts/design/current-collection-detail.png`

## What I found when I went back and looked

1. **Tags are in the API, not in the UI.** Every collection already has a `tags: string[]` field populated from the backend (e.g. `["surround", "french", "2026"]` on Accessibility). The frontend `Collection` TS type does not declare it, so every card and every detail view silently drops it.
2. **Custom metadata on the detail page reads like an admin tool.** Currently it's an MUI `<Table>` with "Key / Value" headers. Functional but jarring — nothing else on the page looks like a spreadsheet.
3. **Sub-collection cards use a different component than the main list cards.** `CollectionsPage` renders its grid with an inline card (thumbnail 180px tall). `CollectionViewPage` renders sub-collection children with `CollectionCardSimple` (thumbnail 120px tall, different padding, different typography). Two cards, two shapes, same data.
4. **Thumbnail dimensions are inconsistent across the app.** The list page is a fixed height (180px), the sub-collection card is fixed height (120px), and with the redesign proposal I locked the list card to 1:1 aspect ratio but didn't address the sub-collection card. The user wants one ratio everywhere.
5. **No description, no tags, no owner, no dates surfaced at the top of the detail page.** The header is "Breadcrumbs + action buttons" and goes straight into the metadata table. There's no summary panel that tells you what this collection is.

## Scope additions

### A. Tag support, everywhere

**Card (list and sub-collection grid)** — below the description line, above the meta row, show up to 3 tag chips. 4th+ collapses into a `+N` overflow chip. Tags are click-through: clicking a tag scopes the list to that tag filter (uses a new `filter[tag]=<value>` query param we'll add).

```
┌──────────────────────┐
│     [thumbnail]   🌐 │
│                      │
│  Accessibility    ⋯ │
│  Department · all…   │
│  ┌───┐┌────────┐    │
│  │q2 ││ french │+1  │  ← tag row
│  └───┘└────────┘    │
│  ─────────────────   │
│  10 sub · 0 assets   │
│               Apr 27 │
└──────────────────────┘
```

**Detail page header** — tags render as a horizontal row of chips right under the collection title, alongside the visibility badge and owner byline. Same chip style as the card so the two views feel related.

Implementation note: add `tags?: string[]` to the FE `Collection` interface in `useCollections.ts`. Add `filter_tag` to `ListCollectionsQueryParams` on the backend (mirrors `filter_type`/`filter_ownerId`). Add a `{"term": {"tags": value}}` filter to `search_collections`. No migration — `tags` is already in the OpenSearch mapping and already populated.

### B. Collection detail page — new structure

Replace the current "breadcrumbs → metadata table → sub-collection grid" with a three-band layout that mirrors the rhythm of the list page:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Home › Collections › Accessibility                   [+ Sub] [Edit] [⋯]    │  ← breadcrumbs + actions
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────┐   Accessibility                             🌐 Public         │
│   │          │   Accessibility department - all accessibility                │
│   │  thumb   │   projects and assets                                          │
│   │   1:1    │                                                                │
│   │          │   #surround #french #2026                   ← tag chip row    │
│   └──────────┘                                                                │
│                  Owner   @medialake+dev3    Created Apr 28   Updated Apr 28  │
│                  Items   0 assets · 10 sub-collections                       │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  Metadata                                            [Edit]                  │  ← metadata card
│  ┌─ priority ──────┐┌─ campaign ──────┐┌─ department ──┐                    │
│  │  P1             ││  Q1-2026-Brand  ││  Creative     │                    │
│  └─────────────────┘└─────────────────┘└───────────────┘                    │
│  ┌─ budget ────────┐┌─ owner-contact ─┐                                     │
│  │  $42,000        ││  jane@example   │                                     │
│  └─────────────────┘└─────────────────┘                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  Sub-Collections (10)                                                        │  ← same card grid as list page
│  [card] [card] [card] [card] [card]                                          │
│  [card] [card] [card] [card] [card]                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│  Assets (0)                                                                  │
│  (existing asset grid)                                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Header band**:

- Breadcrumbs on the left (unchanged).
- Action cluster on the right: primary "Create Sub-Collection" (owner/editor), outlined "Edit" (owner/editor), `⋯` for Share/Delete (owner only). Matches the list page's permission gating.

**Summary band** (replaces the spartan title row):

- 128×128 thumbnail tile on the left, 1:1 aspect ratio, rounded 14px. Same aspect ratio as the list cards so an uploaded image looks identical in both places.
- Title (24px bold), description (14px `text.secondary`, 2-line clamp), tag chip row, and a two-column "label → value" grid (Owner / Created / Updated / Items) in a single `Stack`.
- Visibility badge as a pill chip in the top-right of the band, same component as the card badge.

**Metadata card** (replaces the table):

- Card with a header row ("Metadata" + optional "Edit" button that opens the existing edit modal deep-linked to the metadata section).
- Key/value pairs render as a responsive flex-wrap grid of tile chips, each tile showing the key as a small uppercase label above a monospace value. Works whether there are 1 or 40 keys. Only shown when `Object.keys(customMetadata).length > 0`.
- When a key is long or a value is multi-word, the tile grows; chips wrap gracefully. This reads like a data dashboard, not a database admin screen.

**Sub-collection grid**:

- Uses the exact same card component as the list page. Delete `CollectionCardSimple` (or repurpose it only for dashboard widgets). Same 1:1 thumbnail, same hierarchy, same actions menu. This is the single most important consistency win.

**Assets section**:

- Unchanged behavior. Keep existing asset grid/table.

### C. Thumbnail aspect ratio — one rule, enforced everywhere

- **1:1 square** is the canonical ratio. Used on:
  - List page card thumbnail (`CollectionsPage`)
  - Detail page summary tile
  - Sub-collection grid card (inherited from `CollectionsPage` once we unify)
  - Dashboard widget card (if used; same component)
  - Edit modal preview
- CSS: `aspect-ratio: 1 / 1; width: 100%;` (no fixed pixel height). Means the card naturally resizes with the grid column width; on mobile it's small, on desktop it's large, always square.
- The Pillow resize on the backend already enforces max 512×512 fit-within, so uploaded images that aren't square get letterboxed — which on a 1:1 tile with `object-fit: cover` means a centered crop. That's acceptable and consistent.
- Fallback (no thumbnail): same square tile, accent-tinted background, centered collection-type icon. Icon size scales with the tile (`48px` when tile is ~160px wide, `64px` at ~200px, etc.).

### D. Card size: one knob

Add one CSS variable `--collection-card-min-width: 220px` used by the grid's `grid-template-columns: repeat(auto-fill, minmax(var(--collection-card-min-width), 1fr))`. That lets the redesign accommodate future "card size" user preference (small/medium/large) from a single place, mirroring how the Search `Appearance` panel already works for assets.

## What's in v1 now vs later

**v1 (expanded from original):**

- Toolbar strip + Sort popover with standard + custom-metadata sections
- Backend sort regex extension
- Card refresh: always-visible actions, visibility badge, description line, **tag chip row**, active-sort chip, 1:1 thumbnail
- FE Collection type: add `tags?: string[]`
- Backend: add `filter[tag]=<value>` query param + filter clause
- **Collection detail page refresh: summary band + tag row + metadata tile grid + unified sub-collection cards**
- Retire `CollectionCardSimple` (or scope it to dashboard-widget only)

**v1.1 (deferred):**

- List view on the list page
- Clickable tag chips → scope list to that tag (uses the new backend filter from v1)
- Numeric-aware sort for metadata keys with numeric values
- Saved views

## Open questions for review (round 2)

4. **Tag chips on cards: 3 visible + "+N" overflow, or infinite wrap (can push meta row down)?** Proposal: capped at 3 to keep card heights uniform.
5. **Metadata tiles on the detail page: "Edit" button per-tile or one button on the section header?** Proposal: single header button, opens the existing edit modal scrolled to the metadata section. Avoids per-tile chrome.
6. **Tile grid vs. two-column "label: value" list for metadata?** Proposal: tiles. They scan better, they scale from 1 to 40 entries without awkwardness, and they echo the chip language used for tags.
7. **Single thumbnail ratio confirmed as 1:1 everywhere?** Needed before I touch any component — also drives the `CollectionCardSimple` retirement.

---

# Addendum v3 — Filter Drawer Model

> **Added:** 2026-04-28 (round 3)
> **Trigger:** Reviewer asked how the filter model behaves when adding filters; wanted it visible in the primary view.
> **Preview:** Third column of `collections-redesign-preview.html` + `proposal-list-with-filter-{light,dark}.png`

## Shape

A right-docked **drawer**, same pattern the Search page uses. Pops in from the right edge, does not cover the card grid, shares the page's height. Desktop-first; on narrow viewports it collapses to a full-screen overlay (pure CSS — no JS breakpoint needed).

Four sections stacked vertically with a shared header and a sticky footer. Each section is collapsible and shows a count pill when it has active filters.

```
┌──────────────────────────────────────┐
│  Filter collections              ✕  │
│  4 active · 2,020 results            │
├──────────────────────────────────────┤
│  VISIBILITY                     [1]  │
│  ☑ Public                     1,214  │
│  ☐ Shared with me               608  │
│  ☐ Private                      198  │
├──────────────────────────────────────┤
│  COLLECTION TYPE                     │
│  ☐ Campaign                     412  │
│  ☐ Project                      356  │
│  ☐ Batch                        289  │
├──────────────────────────────────────┤
│  TAGS                           [2]  │
│  ☑ french                       142  │
│  ☑ 2026                         980  │
│  ☐ q2                           305  │
│  ☐ 8k                           212  │
├──────────────────────────────────────┤
│  CUSTOM METADATA                [1]  │
│  [department ▾] [Marketing   ] [✕]   │
│  [Select key…] [value        ] [✕]   │
│  [+ Add metadata filter]             │
├──────────────────────────────────────┤
│  UPDATED                             │
│  ☐ Last 24 hours                     │
│  ☐ Last 7 days                       │
│  ☐ Last 30 days                      │
├──────────────────────────────────────┤
│          [Reset all]  [Apply · 2020] │
└──────────────────────────────────────┘
```

## Behavior

- **Drawer is a draft state**. Picking a filter doesn't fire a network request. The footer's "Apply" button commits the draft; "Reset all" clears it back to the last applied state. Mirrors the Search page's `applyFilterModalDraft()` pattern in `searchStore.ts`.
- **Result count updates live in the draft**. As the user toggles filters, the Apply button label updates (`Apply · 2,020` → `Apply · 142`) using a cached OpenSearch `count` request fired on a 250ms debounce. Keeps the commit obvious while avoiding a spinner flash.
- **Section counts come from OpenSearch aggregations**. We fire one agg-only search (aggs for visibility, collectionType, tags, updated) alongside the main list query. No extra round-trip from the user's perspective.
- **Backend uses `post_filter`** for the facets that are multi-select OR-grouped within themselves, so a user selecting "french + 2026" in Tags gets counts for all other tag values unaffected. Same pattern the search API already uses.
- **Closing the drawer**:
  - via `✕` or backdrop click: discards uncommitted draft (existing Search-page behavior); or
  - via Apply: commits and closes.
- **Active filters persist in the URL** as query params (`filter[tag]=french&filter[tag]=2026&filter[visibility]=public&filter[metadata.department]=Marketing`). Shareable, back-button-safe, hydratable on page load.

## Filter types (v1)

| Section         | Input                                                                                               | Backend query param                              | OpenSearch clause                                    |
| --------------- | --------------------------------------------------------------------------------------------------- | ------------------------------------------------ | ---------------------------------------------------- |
| Visibility      | multi-checkbox (public / shared with me / private)                                                  | `filter[visibility]=public,shared,private`       | `terms` on `isPublic` + `sharedWithMe` + computed    |
| Collection type | multi-checkbox, populated from `useCollectionCollectionTypes()`                                     | `filter[type]=<typeId>`                          | `terms` on `collectionTypeId.keyword`                |
| Tags            | multi-checkbox, populated from a new `/collections/tags` endpoint (aggregation over `tags.keyword`) | `filter[tag]=<value>` (repeatable)               | `terms` on `tags.keyword`                            |
| Custom metadata | repeatable key/value row                                                                            | `filter[metadata.<key>]=<value>` (already wired) | `fuzzy` on `customMetadata.<key>.keyword` (existing) |
| Updated         | single-select radio                                                                                 | `filter[updatedWithin]=24h\|7d\|30d`             | `range` on `updatedAt`                               |

## Active-state surface on the primary view

Two places reinforce what's filtered, so users never feel lost:

1. **Trigger button badge** — the toolbar "Filters" button shows a numeric badge with active-filter count (pattern already in the prototype: `Filters [2]`). Clicking it reopens the drawer with the current committed state loaded into the draft.
2. **Chip row below the toolbar** — each active filter becomes a dismissible chip (`Public ×`, `#french ×`, `department = Marketing ×`). Clicking a chip removes just that filter without opening the drawer. This row is the same one showing active Sort and Search (see preview row in the first mock), so users have one strip that says "here's why you're seeing these results".

## What this replaces

The old inline metadata-key + metadata-value row on the toolbar (`MenuItem` + `TextField` side by side) is retired. All filtering lives in the drawer + the chip row, freeing the toolbar to hold only Search / Sort / Filters trigger / View toggle.

## Deferred to v1.1

- Saved filter sets (name a combination, save it under a tab like "My roster")
- Count-sorted vs alphabetically-sorted rows inside each section (v1 defaults to count descending)
- Numeric range filter on custom-metadata values (requires numeric-detection at index time)
- "Invert" toggle per section (e.g. "NOT public")

# Collection Cards — Metadata Visibility & Customization Proposal

> Status: Proposal only. No code changes. Ready for review.
> Scope: `medialake_user_interface/src/components/collections/CollectionCard.tsx`,
> `CollectionsPage.tsx`, `CollectionViewControls.tsx`, plus a small `useCollectionViewPreferences` hook.

---

## 1. Validation of the reported gap

I read the current implementations end-to-end. The report is accurate: **custom metadata does not render on collection cards today, only on the detail page.**

### What the card renders now (`CollectionCard.tsx`)

Top → bottom:

1. Thumbnail (edge-to-edge, 180px tall). Uploaded image, icon, or fallback.
2. Optional parent breadcrumb (only when `parentName` is passed — used for flat search results).
3. Name (single line, ellipsized).
4. Description (2-line clamp).
5. **A single `customMetadata` chip — but only for the key currently being sorted on** (`sortedMetadataKey`).
6. Tags, capped at 3 with a `+N` overflow chip.
7. Meta row: `N sub · M assets · date` on the left, visibility chip on the right.

### What the detail page renders (`CollectionViewPage.tsx` ~L1088-1190)

A full `Metadata` tile grid showing **every** `customMetadata` key/value pair in a responsive `minmax(200px, 1fr)` grid with monospace values.

### The gap

`Collection.customMetadata` (`Record<string, string>`) is shipped on every collection in the list response, but it's only surfaced on the card as a single chip tied to the active sort. So:

- If a user sorts by `name`, **none** of their custom metadata ever appears on cards — even though it's the primary reason most teams enable custom metadata in the first place.
- Users can't scan a library of collections by `priority`, `client`, `episode_number`, etc., which forces them into the detail page for every card they consider.
- There's no parity with `AssetViewControls` on the Search page, where users pick exactly which fields appear on each asset card.

---

## 2. Learning from Search (the pattern to mirror)

The Search page already solves this problem well. Reusing its mental model keeps the product consistent and the implementation lightweight.

### `AssetViewControls.tsx` — "Fields" popover

- Lists **all available fields** (standard + custom).
- Checkboxes toggle visibility per field.
- "Show all / Hide all" text action in the header.
- Custom fields are grouped below a divider with a `CUSTOM FIELDS` overline.
- State persists via `useViewPreferences` (or `useMetadataFieldPreferences` when available).

### `AssetCard` / `AssetGridView`

- Card renders only the fields whose `visible: true`.
- Supports a `cardSize` (small / medium / large) and `aspectRatio`.
- A master `showMetadata` toggle hides the entire metadata block for an image-first view.

### Why this fits collections too

Collections already have a **Sort** popover in `CollectionViewControls` that separates `Standard fields` from `Custom metadata`. The same split reads cleanly in a **Display** popover for cards — users get a consistent "choose fields" gesture on both pages.

---

## 3. Proposed card presets + fine-grained control

The request asks for presets ("all metadata", "tags and metadata", "tags and description", "just image"). I'd implement both:

### A. Four built-in density presets

| Preset                               | Renders                                                                                                         |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------------- |
| **`full`**                           | Thumbnail + name + description + **all** custom metadata + tags + meta row + visibility                         |
| **`rich`** _(default for new users)_ | Thumbnail + name + description + **top N** custom metadata (default 3) + tags + meta row + visibility           |
| **`compact`**                        | Thumbnail + name + tags + meta row + visibility. Description and metadata hidden.                               |
| **`minimal`**                        | Thumbnail + name only. Visibility still shown as a 1px corner pip on the thumbnail to preserve a safety signal. |

Presets are a **one-click** choice from a new `View` trigger in `CollectionViewControls`, rendered as a segmented toggle in the popover (same pattern as Search's `cardSize`).

### B. Expert mode — explicit field checkboxes

Under the presets, an expandable `Customize fields` section (collapsed by default) with checkboxes for:

- Description
- Tags
- Item / sub counts
- Updated date
- Visibility badge
- Parent breadcrumb (auto-hidden when not applicable)
- **Custom metadata fields** — one checkbox per key surfaced by `/collections/metadata-keys` (the same endpoint that feeds the Sort popover's custom section, so no new backend work).

Selecting any checkbox switches the preset indicator to **`Custom`**. Picking a preset resets checkboxes to that preset's profile.

### C. Visual density controls (mirrors Search)

- **Card size**: `small | medium | large` — maps to the grid's `minmax(Wpx, 1fr)` (currently fixed at `280px`). Suggested values: 220 / 280 / 340.
- **Thumbnail height**: derived from card size; keeps the 16:9-ish ratio at each width.
- **Show metadata toggle**: quick hide-everything-below-name switch (accessible hotkey).

---

## 4. Card rendering changes (details)

### 4.1 Add a `CollectionCardDisplay` contract

```ts
export type CollectionCardPreset =
  | "full"
  | "rich"
  | "compact"
  | "minimal"
  | "custom";

export interface CollectionCardDisplayPrefs {
  preset: CollectionCardPreset;
  showDescription: boolean;
  showTags: boolean;
  showMeta: boolean; // item/sub counts + updated date
  showVisibility: boolean;
  showParentBreadcrumb: boolean;
  /** Which customMetadata keys to render, in order. Empty = none. */
  visibleMetadataKeys: string[];
  /** Soft cap when preset=rich. Hard cap for visual stability. */
  maxMetadataKeys: number;
  cardSize: "small" | "medium" | "large";
}
```

Pass this in as a single `display` prop, plus the current `collection`, action handlers, and style props. This keeps the per-call site tidy.

### 4.2 New "Metadata strip" on the card

Goes **below the description, above tags**. Dense, scannable, capped.

- Layout: `key: value` pairs, each as a tiny outlined chip (monospace value, sans-serif key).
- Key label is uppercase, 0.6rem, text.disabled — same vocabulary as the detail-page tile grid.
- Value is monospace — echoes the detail page so users get the same "this is data" cue.
- Truncates with ellipsis at chip level; title attr shows full value on hover.
- Cap: `maxMetadataKeys` (default 3 in `rich`, unbounded in `full`). Overflow shows `+N more` chip linking to the detail page.
- If zero visible keys have values on this collection, the strip collapses to nothing — never a ghost block.

### 4.3 Change the existing `sortedMetadataKey` chip

Becomes **redundant** once the strip exists: the sorted key is now naturally visible. Keep it only when preset = `minimal` (user opted out of metadata but we should still explain sort order). Otherwise remove.

### 4.4 Respect `cardSize`

Today the card is a fixed layout. Under `small`, the description clamps to 1 line, tags cap at 2, metadata strip hidden. Under `large`, description clamps to 3 lines, tags cap at 5, metadata strip shows up to 5 keys.

### 4.5 `minimal` preset — preserve visibility signal

An absolute preset that strips the info section entirely is punchy but loses a safety cue. Compromise: overlay a **4×4 dot** on the thumbnail, colored by visibility (green/amber/grey). Tooltip on hover states `Public | Shared | Private`. This keeps `minimal` truly image-first without sacrificing a critical read.

---

## 5. Toolbar changes — `CollectionViewControls`

Add one new trigger button to the right of **Sort** and **Filters**:

```
[ Search… ]                     [ Sort ▾ ]  [ Filters ▾ ]  [ View ▾ ]
```

The **View** popover has three sections:

1. **Preset** — 4-up segmented pill (`Full | Rich | Compact | Minimal`). Current selection highlighted in primary.
2. **Card size** — 3-up segmented pill (`S | M | L`) matching Search.
3. **Customize fields** — collapsed summary (`3 of 8 fields`) that expands into checkboxes on click. Sections:
   - `Core` — Description, Tags, Meta, Visibility, Breadcrumb
   - `Custom metadata` — one row per key from `useGetMetadataKeys` (already fetched for Sort).

Popover styling matches `AssetViewControls`'s `popoverPaperSx` and section labels verbatim so the two feel like siblings.

---

## 6. State + persistence

A small dedicated hook, intentionally separate from `useViewPreferences` (which is tied to asset card fields):

```ts
// medialake_user_interface/src/hooks/useCollectionViewPreferences.ts
export function useCollectionViewPreferences() { … }
```

- Defaults: `preset: "rich"`, `cardSize: "medium"`, `maxMetadataKeys: 3`, `visibleMetadataKeys` seeded from the top 3 most common keys once `/collections/metadata-keys` resolves (empty until then).
- Persistence: `localStorage` under a single key `medialake.collectionViewPrefs.v1`, debounced writes. Safe to ignore read errors and fall back to defaults.
- Migration-proof: wrap with `z.object(...).safeParse` (zod is already a dep) so future field additions don't blow up saved prefs.
- Hook returns `{ prefs, setPreset, setCardSize, toggleField, setVisibleMetadataKeys, resetToPreset }`.

---

## 7. Backend touch points

**None required.** Everything needed is already returned by `/collections` and `/collections/metadata-keys`:

- `collection.customMetadata: Record<string, string>` — already in the list response.
- `collection.tags: string[]` — already surfaced.
- Metadata keys endpoint — already consumed by the Sort popover.

This is a pure UI change.

---

## 8. Accessibility + testing

- **Keyboard**: View popover is a standard MUI `Menu`; preset toggle is a `ToggleButtonGroup` (already keyboard-accessible). Checkboxes get the usual role/label treatment.
- **Screen readers**: Each metadata chip gets `aria-label={`${key}: ${value}`}`. The visibility dot in `minimal` keeps its `aria-label` so the text reading is unchanged.
- **Snapshot tests**: `CollectionCard.test.tsx` gets parametrized cases for each preset × `cardSize` combination (4×3 = 12) so regressions in the density grid are caught.
- **Playwright**: Add one spec verifying preset persistence across reload and that `+N more` links to the detail page. Extend `collection-opensearch-listing.spec.ts`.

---

## 9. Rollout plan

Phased so we can land each piece independently:

1. **Phase 1 — Data surface** _(pure addition, no toolbar)_: render a default `rich` metadata strip on every card (top 3 keys, alphabetical). Ships the missing visibility immediately, zero regression risk. (Small PR.)
2. **Phase 2 — Presets**: introduce `preset` + segmented `View` trigger. Default `rich`. Remove redundant `sortedMetadataKey` chip except in `minimal`.
3. **Phase 3 — Custom fields**: `useCollectionViewPreferences` hook + checkboxes, keyed off `/collections/metadata-keys`. Persists to localStorage.
4. **Phase 4 — Card size**: wire `cardSize` into grid `minmax(...)`. Reuse Search's segmented control.

Each phase is shippable on its own and doesn't block the next.

---

## 10. Open questions for the user

1. **Default preset** — `rich` is my recommendation (solves the reported gap without changing other defaults). Confirm?
2. **Default `visibleMetadataKeys` for a brand-new tenant** — top 3 keys by frequency across the tenant's collections (requires a small aggregation at the metadata-keys endpoint) vs. just the first 3 alphabetically (zero backend work)? I'd start alphabetical and revisit.
3. **`minimal` preset safety dot** — OK as a compromise, or should `minimal` be truly stripped (name only, no visibility cue)?
4. **Persistence scope** — localStorage (per-device) is fine for now. Do we want to promote to user profile later so prefs follow a user across machines? If yes, plan the endpoint now even if we don't implement it.

---

## 11. What this does _not_ touch

- `CollectionCardSimple` (dashboard widget variant) — intentionally unchanged. Its constraints are different (fixed small size, name + count only). Touching it expands scope.
- Backend schemas, index mappings, OpenSearch documents — no changes.
- Collection detail page metadata tile grid — stays as the canonical full view.
- Filter drawer — out of scope.

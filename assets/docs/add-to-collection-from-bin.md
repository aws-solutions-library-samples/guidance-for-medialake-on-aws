# Add to collection from the bin

Design for adding the bin's selected assets to a collection, gated on permission.

Status: **accepted — all open questions answered, see [Decisions](#decisions).** The backend
and the collection-page display are implemented; the bin's own action is still outstanding.

## Today

The bin (`components/common/RightSidebar/BatchOperations.tsx`) holds a cross-page selection
and offers three bulk actions:

| Action                | Gate                                                                                                                        |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Download              | `useActionPermission("download", "asset").allowed`                                                                          |
| Delete                | `canDelete` prop, defaulting to `useActionPermission("delete", "asset")`                                                    |
| Run a manual pipeline | `canListPipelines && canRunPipelines`, and the section is **hidden** when not permitted so no `GET /v1/pipelines` is issued |

Adding to a collection is available **per asset only** — the card action bar, the asset
header, and the dashboard widgets all open `components/collections/AddToCollectionModal.tsx`
(895 lines: collection browsing, breadcrumbs, inline collection creation). Its props take a
single `assetId: string`.

So a user who has selected twelve assets in the bin must open twelve modals.

## What already exists and should be reused

**The permission hook.** `useCollectionAssetPermissions()` returns `canAdd`, which is
`can("add_assets", "collection") || can("edit", "collection")`, and returns `false` while
the ability is still loading so no unauthorized affordance flashes.

**Two-layer authorization, already correct.** `canAdd` is the coarse tenant-wide
permission. The specific collection additionally requires an EDITOR role, enforced
server-side in `collections_ID_items_post.py`:

```python
collection, _ = require_collection_role(collection_id, user_id, minimum_role="EDITOR")
```

with the client-side mirror `isAddable(c)` — `status === "ACTIVE"` and
`userRole ∈ {owner, admin, editor}`. **Both layers must be honoured**: `canAdd` decides
whether the affordance appears at all, `isAddable` decides which collections are offerable.
A user can legitimately have `canAdd` and zero addable collections.

**The modal.** Reusing `AddToCollectionModal` keeps one collection-picking UX, including
inline creation, rather than growing a second picker.

## Constraints found in the current implementation

**1. The endpoint is single-asset.** `POST /collections/{id}/items` takes
`AddItemToCollectionRequest{ assetId, clipBoundary?, addAllClips? }`. It expands one asset
into multiple _items_ when clips exist, but there is no way to submit several assets.
Adding N assets is therefore N requests unless the endpoint is extended.

**2. The bin can hold clips, not just whole assets.** Bin entries carry
`segment?: { startTime, endTime, label? }` and render as `name (0:12–0:45)`. So "add the
selection to a collection" has to decide what a clip entry means, and the endpoint already
has the vocabulary for it (`clipBoundary`, `addAllClips`).

**3. Re-adding is an overwrite, but `itemCount` still increments.** Items are written with
PynamoDB `item.save()` and no condition, so re-adding the same asset+clip silently
overwrites — no error, no duplicate row. However `itemCount` is incremented by
`len(added_items)` regardless, so repeated adds inflate it. The code already notes
`itemCount` is deprecated in favour of a computed count. Bulk-adding from the bin makes
this easier to hit, so the spec should say whether it is in scope.

## Proposed design

### Placement and gating

A single "Add to collection" action in the bin's quick-actions row, alongside download and
delete. **Hidden, not disabled, when `!canAdd`** — matching how the pipeline section and
(as of the recent fix) the per-asset download icon behave, so an unpermitted user is never
offered a control that would 403. The row's existing `hasQuickActions` guard extends to
`canDownload || canDelete || canAdd`.

### Flow

1. User selects assets across pages; they accumulate in the bin.
2. User clicks **Add to collection**.
3. `AddToCollectionModal` opens in multi-asset mode, showing the selection count and
   offering only `isAddable` collections.
4. On confirm, the assets are submitted (see open question 1).
5. Result is reported, and the bin is updated per open question 3.

### Modal change

Widen the props to accept a set rather than a single id, keeping the existing single-asset
call sites working:

```ts
// before
assetId: string;
// after — exactly one of these
assetId?: string;
assetIds?: string[];
```

with a normalisation step inside so the body of the component only ever deals with an
array. Six call sites currently pass `assetId`; none need to change.

The confirm button and headline become count-aware, which introduces plural i18n keys.
**These must be added to all 11 locales**, not just `en.ts` — the saved-upload-destinations
feature shipped `en.ts` only and that accounted for the entirety of
`check-locale-completeness`'s 90-key backlog.

### Reporting

Adding 12 assets can partially succeed: some already present, some failing authorization
(the collection's role check is per-collection, not per-asset, so this is unlikely but
possible if the role changes mid-flight), some failing transiently. The design should
surface "10 added, 2 already in this collection, 1 failed" rather than a bare success, and
must not claim success for assets that failed.

## Testing

- `canAdd` true/false → action present/absent, and the bin still opens and works either way
  (the bin regression that motivated the pipeline gating).
- Quick-actions row layout with the action shown and hidden — no gap, no orphaned divider,
  matching the checks used on the card action bar.
- Only `isAddable` collections offered; `canAdd` with zero addable collections.
- Multi-asset submit: all-success, partial, all-fail.
- Clip entries behave per the decision in open question 2.
- Single-asset call sites unchanged (regression cover for the widened props).

## Decisions

All six open questions are answered; this section is the record.

| #   | Question                                 | Decision                                                                                                                                             |
| --- | ---------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Bulk endpoint or N client requests?      | **Extend the endpoint**, keeping it backwards compatible                                                                                             |
| 2   | What does a clip entry mean?             | **Preserve the clip boundary** in the collection                                                                                                     |
| 3   | Bin after a successful add?              | **Keep it**, but tell the user clearly whether it succeeded                                                                                          |
| 4   | Selection cap?                           | **No cap on what a user may select**; the client batches a large selection across requests (see [Request size is bounded](#request-size-is-bounded)) |
| 5   | Inline collection creation from the bin? | **Yes**, consistent with the other modals, with the UI conditional on permissions                                                                    |
| 6   | `itemCount` inflation?                   | **Fix it**                                                                                                                                           |

### How the endpoint stays backwards compatible (1)

`POST /collections/{id}/items` accepts two mutually exclusive shapes:

```jsonc
// unchanged — every existing caller keeps working
{ "assetId": "asset:uuid:1", "clipBoundary": {...}, "addAllClips": false }

// added
{ "items": [
    { "assetId": "asset:uuid:1" },
    { "assetId": "asset:uuid:2", "clipBoundary": { "startTime": "...", "endTime": "..." } }
] }
```

A flat `assetIds: string[]` was rejected because decision 2 requires a boundary **per
asset** — the bin can hold clips of several different assets. `sortOrder` and `metadata`
stay request-level, exactly as before. Supplying both shapes, neither, or an empty `items`
list is rejected, so the request is never ambiguous about whether the request-level
`clipBoundary` applies to the list.

The response gains counts alongside the existing `addedCount` and `items`, so the client
can report the outcome required by decision 3 rather than a bare success:

```jsonc
{ "addedCount": 10, "alreadyPresentCount": 2, "failedCount": 1,
  "results": [ { "assetId": "...", "status": "alreadyPresent" } ], "items": [ ... ] }
```

### How `itemCount` is fixed (6)

The write becomes conditional on the row not already existing
(`item.save(CollectionItemModel.SK.does_not_exist())`). Two consequences:

- `itemCount` is incremented only by the number of genuinely new rows, so repeat adds no
  longer inflate it.
- A re-added asset keeps its original `addedAt`/`addedBy` instead of being silently
  re-stamped. This is a deliberate behaviour change: "add" is now idempotent rather than an
  upsert, so a caller re-posting with new `metadata` no longer overwrites the stored value.

A failed condition is classified as `alreadyPresent`; any other error — including one that
cannot be classified — is `failed`. The classifier reads PynamoDB's structured cause code,
never the message text, and the ambiguous case deliberately resolves to `failed`: claiming
"already present" for a write that actually failed silently drops what the user asked for,
whereas `failed` prompts a retry, and retrying a genuine duplicate is a no-op now that adds
are idempotent. Message matching could only produce the unsafe direction, since PynamoDB
formats the wrapped botocore string into every `PutError` message, not just this one.

If _every_ write failed and nothing ended up in the collection, the endpoint returns 500
rather than 201. A partial failure still returns 201, with `failedCount` and `results`
describing what did not land, and items that were already present count as not-a-failure
because the collection does hold them. This corrects pre-existing behaviour — `main` also
swallowed `PutError` and answered 201 — which mattered most for legacy single-asset callers,
since they check the status code and nothing else.

### Request size is bounded

Decision 4 was "no cap", and that holds for the product: a user may select any number of
assets in the bin. It cannot hold for a single HTTP request, though, so the cap is a transport
bound and the client is responsible for splitting a larger selection into
`MAX_ITEMS_PER_REQUEST`-sized batches (default 250, env-overridable) and aggregating the
per-batch counts into one message.

A request is rejected with 400 if it names more than that many assets, or if it _resolves_ to
more than that many rows — `addAllClips` expands one asset into one item per clip, so a small
request can still fan out.

The cap alone is not a timing guarantee, and shouldn't be mistaken for one: it bounds how many
writes are queued, not how long each takes, so a few hundred slow writes could still exceed
API Gateway's 29s window. The handler therefore also stops while Lambda budget remains
(`WRITE_DEADLINE_RESERVE_MS`, default 5s) and returns the items it did not attempt under
`notAttemptedCount`, with a `notAttempted` entry per asset in `results`. Those were never
written and are safe to retry.

Without that, exhausting the window kills the request mid-loop: the caller gets no response
while part of its selection is already persisted, and cannot tell which part. Stopping early
turns that into an ordinary response the client can act on.

Lifting the per-request bound entirely means moving bulk adds to an asynchronous job with
durable progress and aggregated results — a larger change than this feature needs, and not
required as long as the client batches.

## Known limitations

**Duplicate rows across the two key formats — prevented on write, not retrospectively.**

The conditional write guarantees uniqueness of the canonical `ASSET#{id}#FULL` /
`ASSET#{id}#CLIP#{range}` key only. Collections created before that key can also hold a legacy
`ITEM#{uuid}` row for the same asset, where the SK carries a uuid rather than the asset id, so
the condition cannot see it. Left alone, adding such an asset again would store it twice —
both rows returned by GET, both counted in `itemCount`.

Adds now read the collection's legacy rows once per request and report a match as
`alreadyPresent` instead of writing a second row. This is a read-then-check, which is sound
here because nothing creates `ITEM#` rows any more — every writer goes through
`generate_asset_sk` — so the legacy set can only shrink, never grow. A row deleted between the
read and the write merely reports an add as already present; the caller retries and it
succeeds. The read is projected to three attributes, costs one query per request rather than
per item, is bounded by `MAX_LEGACY_ROWS_SCANNED` (2000) so a large legacy collection cannot
make every add slow, and on failure is treated as "no legacy rows" — this check exists to
avoid a duplicate and must not be the reason an add fails.

What this does **not** do is repair duplicates already in the data, or the `itemCount` values
already inflated by them. That needs a backfill onto the canonical key, which is its own piece
of work. Read-time deduplication was considered and rejected: hiding one of the two rows would
leave it unreachable, including for the delete endpoint that addresses items by SK.

## Open questions

None — see Decisions above.

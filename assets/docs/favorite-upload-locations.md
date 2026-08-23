# Saved Upload Locations — Design

> **Phase 1 is implemented.** What shipped and what was deliberately deferred is set out in
> [Phasing](#phasing). Remaining open questions are at the [end](#open-questions).

## Overview

Users repeatedly upload to the same handful of places. Before this, every upload required
re-picking a connector and re-walking the S3 prefix tree.

Phase 1 does two things:

- **Remembers the last location you uploaded to** and restores it the next time the uploader
  opens. This is the zero-configuration behaviour that auto-populates the destination.
- **Lets you save destinations** (add and delete) so they can be picked directly from the
  destination dropdown.

A saved location captures the connector, the path, **and** any collections that were
selected — so "Client A dailies" can mean "that prefix _and_ the Client A collection".

## Grounding: what an "upload spot" actually is

An upload destination is fully identified by **`(connectorId, path)`**:

- `FileUploader` holds exactly two pieces of destination state: `selectedConnector` (a
  connector id) and `uploadPath` (a prefix string).
- The bucket is **never** client-supplied. `post_upload/index.py` derives it from
  `connector["storageIdentifier"]` after a `get_item` on the connector table.
- The path is validated server-side against the connector's `objectPrefix` allow-list
  (`validate_prefix_access`), normalised through `os.path.normpath`, and — for personal
  connectors — required to start with `personal/{user_sub}/` (`validate_personal_path`).
- Non-personal connectors additionally require `connectors:upload`, enforced inside the
  Lambda by `caller_can_upload_to_connectors`. Note this permission is **not** in the
  authorizer route map; it is enforced only in the handler and mirrored in the UI via
  `can("upload", "connector")`.

`connectorId` may be the My Assets (personal) connector, so "My Assets + path" is a valid
saved location. An empty path is also valid and means "the connector's default root" —
FileUploader's existing effect then fills in `allowedPrefixes[0]`.

**Consequence: a saved destination introduces no new trust boundary.** Every upload
re-resolves and re-validates the connector, the prefix allow-list, personal-path ownership,
and `connectors:upload`. A stale saved location pointing at a deleted connector 404s; one
pointing at a connector the user lost access to 403s. The client still filters unusable
entries, but for UX, not for security.

## Phasing

|               | Phase 1 (implemented)                          | Later                                                                    |
| ------------- | ---------------------------------------------- | ------------------------------------------------------------------------ |
| Auto-populate | last-used location                             | a favorite marked **default**, which will take precedence over last-used |
| Favorites     | add, delete                                    | rename, reorder                                                          |
| Labels        | auto-derived `"{connectorName} / {path}"`      | user-editable                                                            |
| Management UI | the star toggle in the uploader                | a list on `settings/profile`                                             |
| My Assets     | one opaque destination; root only, path hidden | browsing inside it, which would make sub-paths savable                   |

The stored shape already accommodates all of the deferred work: `defaultId` exists as a
pointer (written as `null`, ignored on read), entries carry a stable `id` and a `label`, and
`locations` is an ordered array. Landing the later phases is a client change plus, for
rename, nothing at all server-side.

## The central structural problem

The destination control was keyed on connector id alone (`value={selectedConnector}`), which
**cannot represent two saved locations on the same connector with different paths**. So the
control had to change regardless of how locations were stored. Two further constraints fell
out of the existing code:

1. `handleConnectorChange` reset `uploadPath` to `""` on every connector change. Applying a
   saved location must set connector **and** path atomically, or the path is lost. Hence
   `applyUploadLocation`.
2. `destinationCount` counted _connectors_, and the dropdown only renders when it is `> 1`
   (read-only `<Paper>` at exactly 1, blocking `<Alert>` at 0). It now counts _destinations_,
   or a user with one connector and three saved locations on it would see no dropdown.

The dropdown value is now a tagged key — `fav:{id}` or `conn:{connectorId}` — and is
**derived** from `(selectedConnector, uploadPath)` rather than held in its own state. So the
control always reflects reality: browse away from a saved location's path and it falls back
to showing the plain connector entry; browse back and the saved entry lights up again.

## Design decisions

### D1 — Storage: user-settings rows, not favorites rows

Both candidate mechanisms live on the User table (`PK=userId`, `SK=itemKey`; no tenant
dimension — verified that no tenant scoping exists on User-table records anywhere).

|                           | Favorites rows (`/users/favorites`)                                               | Settings rows (`/users/settings`)          |
| ------------------------- | --------------------------------------------------------------------------------- | ------------------------------------------ |
| Row shape                 | one row per item, `SK=FAV#{type}#{reverseTs}`                                     | one row per key, `SK=SETTING#{ns}#{key}`   |
| Backend change            | extend `valid_item_types` in two files, widen the TS union                        | none needed                                |
| Rename                    | **impossible** — no PATCH route; POST creates a _new_ row with a new timestamp SK | trivial                                    |
| Custom ordering           | **impossible** — SK is a reverse timestamp, i.e. insertion order only             | trivial                                    |
| One-and-only-one default  | read-modify-write **across rows**; two tabs can produce two defaults              | atomic within one `put_item`               |
| Read consistency          | `favorites_get.py` uses `ConsistentRead: True`                                    | **no** `ConsistentRead`                    |
| Concurrent mutation       | add/remove are independent rows                                                   | whole-array RMW → lost update between tabs |
| Purge on connector delete | possible via a sparse `gsi4Pk`                                                    | not possible                               |

Reusing `/users/favorites` looks obvious — the repo already has a favorites feature — but it
models "a bookmark pointing at an entity that already has an id". A saved upload location is
a **tuple the user composed**: no server-side entity, needs a label, and will need ordering.
Rename and ordering being _structurally_ impossible is what decided it: both are on the
roadmap, and both would require a new backend route anyway, at which point the reuse
argument evaporates.

Two accepted costs:

- **Lost update across tabs.** Editing the list is a read-modify-write of the whole array.
  Accepted: it is a short list edited rarely by one person. Note the favorites-row design has
  the same problem for the default flag, so this is not a regression against the alternative.
- **Stale read after write.** `settings_get.py` does a plain `query` with no `ConsistentRead`.
  Mitigated the way `useFavorites` already does it: optimistic `setQueryData` in `onMutate`,
  reconcile from the mutation response, and **never invalidate on success** — refetching
  could read back the pre-write value and undo what the user just did.

**Two keys, not one.** Last-used is written after every upload; favorites are edited rarely.
A shared key would make every upload a read-modify-write contending with favorites edits.

### D2 — Backend hardening (done)

Two gaps were closed as part of this work. Both are in shared endpoints, so they are worth
reviewing on their own merits.

**`PUT /users/settings` had no validation of `value` whatsoever** — no schema, no size cap,
no namespace/key allow-list — and until this feature it had **no frontend consumer at all**.
Making it live closed two gaps:

- **Size cap** (`MAX_SETTING_VALUE_BYTES = 64KB`). The endpoint accepts arbitrary JSON by
  design, so a size limit is the only generic protection against a caller bloating their row
  toward DynamoDB's 400KB item limit. Severity was low (self-inflicted, own row only) but it
  was free to close.
- **Rejecting `#` in the namespace or key.** `settings_get.py` parses the sort key
  `SETTING#{namespace}#{key}` by splitting on `#` and taking `parts[1]`/`parts[2]`, so a `#`
  in either would be written successfully and then read back **mis-parsed** — a silent
  correctness bug, since both come straight from the URL path.

Deliberately _not_ added: per-key schema validation, which would couple a generic endpoint to
one feature. The array length cap is enforced client-side and bounded server-side by the size
cap. Still missing and out of scope: there is no DELETE route (removing means writing an
empty value), and `settings_get.py` has no pagination.

**`GET /connectors/s3/explorer/{connector_id}` did not check ownership of personal storage.**
This one is a genuine privacy hole, found while enabling My Assets path browsing.

The explorer resolves the connector by id and validates the requested prefix against _that
connector's_ own `objectPrefix`. My Assets connectors are **per-user** records —
`id = my-assets-{sub}`, `objectPrefix = personal/{sub}/`, created on demand by
`get_my_assets`. So a caller supplying **another user's** connector id would pass the
allow-list check against _their_ prefix and list that user's private files. It needs
`connectors:view` (held by the seeded editor **and** viewer roles) plus knowledge of a
target's Cognito sub.

This predates the feature and is reachable via the API whether or not the UI exposes
browsing, so enabling the My Assets browser does not widen it — but shipping that browser
without fixing it would have been careless. `validate_personal_connector_access` now denies
any personal connector whose owner is not the caller, mirroring how the upload handler
enforces `personal/{user_sub}/` on writes. It runs before prefix handling, since the
allow-list is derived from the connector record and so cannot tell one user's personal
storage from another's.

Ownership is accepted either via `connector["userId"] == caller_sub` or via `objectPrefix`
matching `personal/{caller_sub}/`, so records predating the `userId` attribute still work. A
generic `personal/` prefix does **not** grant access to the whole personal bucket.

The fix is a strict tightening — it only denies access that should never have been granted —
and there is no admin "browse someone else's personal assets" flow that it could break.

### D3 — Saving happens next to the destination, not inside the dropdown

The instinct is a star on each dropdown row. Don't: there is **no precedent anywhere in
`src/`** for an `IconButton` inside a MUI `MenuItem`, and nesting interactive controls inside
an option is an accessibility trap — the option is the click target.

It also matches the real mental model better: you decide a destination is worth keeping
_after_ composing it, including its collections. So the star sits below the destination,
after the path and collection controls, and saves the whole configuration. It carries
`aria-label` **and** `title`, and uses the filled/outline icon-pair convention from
`CollectionFavoriteButton`.

The star deliberately shows **no label text** — the destination is already displayed
immediately above it, so repeating it was pure duplication (and made `getByText("My Assets")`
ambiguous in tests, which is a fair signal).

### D4 — Identity and normalisation

Each entry carries a **`crypto.randomUUID()` id** (the convention in this codebase);
`(connectorId, normalizedPath)` is the _dedup_ key, not the identity. That keeps future
rename/reorder stable and avoids putting a `/`-bearing path into any URL segment.

`normalizeUploadPath` strips leading slashes, collapses `//`, and ensures exactly one
trailing slash, so `projects/a` and `/projects/a/` are one destination rather than two. `""`
and `"/"` both mean "connector default".

### D5 — Collection validation on every upload

`POST /assets/upload` caps the number of collections (`MAX_COLLECTIONS_PER_UPLOAD = 50`) but
**never checks that they exist** — it stamps the ids into S3 user-metadata for a downstream
step. So a saved location could carry ids that silently never resolve.

The uploader now reconciles the selected collections against the live list on **every**
upload, not just when a saved location is applied: the request only ever carries ids that
currently exist and are still _addable_. `isAddable` is reused, so a collection the user has
lost edit rights on is treated the same as a deleted one — equally unusable as a target.

Stale entries are **left visible** in the picker rather than silently deselected: a transient
collections-query failure should not destroy the user's selection. A warning states what will
not be applied. Similarly, when the live list has not loaded yet (`undefined`), everything is
kept rather than wrongly dropped.

Server-side existence validation was considered and rejected for now: presign is called
**per file**, so it would add up to 50 DynamoDB reads per file to the hot path.

### D6 — My Assets is a single, opaque destination

My Assets appears as one destination with **no path dimension**. Browsing inside it is not
offered, and the personal bucket and `personal/{sub}/` prefix are never shown to the user —
the bucket is shared infrastructure and the prefix is an internal detail.

Concretely:

- The path display and Browse button are not rendered when My Assets is selected.
- A saved My Assets location stores `path: ""` — "the connector's default root" — rather than
  the resolved `personal/{sub}/`. So no personal prefix is persisted into user settings, and
  the auto-derived label is just `"My Assets"` rather than `"My Assets / personal/{sub}/"`.
  The prefix-defaulting effect resolves the empty path back to `personal/{sub}/` when the
  location is applied, so uploads still land in the right place.
- The same applies to the remembered last location, which records the persistable path.
- Because there is no way to compose a sub-path, **only the root will ever be saved for My
  Assets** today.

The plumbing to support sub-paths is retained and tested, so enabling it later is a UI
change rather than a data-model change. The prefix is still derived internally (from the
caller's `defaultObjectPrefix`) and used two ways: to default the upload path, and to
validate stored locations — an entry whose path points at `personal/{someone-else}/` is
filtered out with `unavailableReason: "path-not-allowed"` rather than offered.

Path browsing for **shared** connectors is gated on `can("view", "connector")`, because it
calls `GET /connectors/s3/explorer/{id}` which requires `connectors:view`, and `S3Explorer`
issues that request **without** `skipAccessDeniedRedirect` — so for a user lacking the
permission a 403 would bounce them to `/access-denied`, the same failure mode as the
batch-sidebar bug. Hiding the affordance leaves them uploading to the default path.

Personal paths embed the user's own sub, so a My Assets entry is inherently non-shareable —
relevant if group-shared destinations are ever added.

## Data model

`PK = USER#{cognito_sub}`, `SK = SETTING#upload#{key}`.

`favoriteLocations`:

```jsonc
{
  "version": 1,
  "defaultId": null, // reserved for the default-favorite phase
  "locations": [
    {
      "id": "b2c3…", // uuid, stable across future rename/reorder
      "label": "prod-media / projects/clientA/dailies/",
      "connectorId": "conn-123", // may be the My Assets connector
      "path": "projects/clientA/dailies/", // normalised; "" means connector default
      "collections": [{ "id": "col-1", "name": "Client A" }],
      "connectorName": "prod-media", // denormalised for display only
      "storageIdentifier": "prod-media-bkt",
    },
  ],
}
```

`lastLocation`:

```jsonc
{
  "version": 1,
  "connectorId": "conn-123",
  "path": "projects/clientA/dailies/",
  "collections": [{ "id": "col-1", "name": "Client A" }],
  "updatedAt": 1765000000000,
}
```

`version` is checked on read and an unrecognised value is **ignored rather than misread**, so
the shape can evolve without guessing. `defaultId` as a pointer rather than a per-entry
`isDefault` flag makes "exactly one default" a structural invariant instead of something to
enforce; a `defaultId` matching no entry reads as "no default".

Denormalised `connectorName` / `storageIdentifier` are display-only and always re-resolved
against the live connector list — they go stale when a connector is renamed.

## API

No new routes, no CDK change, no authorizer change.

|       |                                                                                      |
| ----- | ------------------------------------------------------------------------------------ |
| Read  | `GET /users/settings?namespace=upload`                                               |
| Write | `PUT /users/settings/upload/{favoriteLocations\|lastLocation}` with `{ "value": … }` |

Neither route appears in the authorizer permission map, so both are already effectively "any
authenticated user" — consistent with `/users/favorites`, which is explicitly mapped to
`None`. The user id comes from `get_authenticated_user_id` (authorizer context, falling back
to `claims.sub`), never from the body.

## Auto-population precedence

Applied in two layers, deliberately:

**Layer 1** (unchanged behaviour) selects My Assets as soon as `defaultConnectorId` is
available, or the sole connector. It still re-fires when `defaultConnectorId` changes, because
`TopBar` passes it as `undefined` until `useMyAssetsConnector` resolves. Keeping it ungated
means the uploader is usable immediately and **never waits on an optional preference
request**.

**Layer 2** then refines to the last-used location once both the saved settings and the
connector list have arrived — but only if:

- the caller has not pinned a destination (`lockConnector`, or an explicit `path` prop). An
  explicit caller intent — "Upload to My Assets", a connector-scoped upload — always wins.
- the user has not already touched the destination. Saved locations load asynchronously, so
  without this guard a slow response could yank the destination out from under someone who
  had already picked one.
- the location is still usable: connector exists and is permitted, and the path is still
  inside its allow-list (skipped for My Assets, whose paths are server-enforced against
  `personal/{sub}/` rather than `objectPrefix`).

When the default-favorite phase lands it slots in ahead of last-used inside layer 2.

## Edge cases

| Case                                                                  | Behaviour                                                                                                                                                       |
| --------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Saved connector deleted / inactive / `allowUploads === false`         | filtered from the dropdown; kept in the stored list with `unavailableReason: "connector-missing"` so future management UI can explain rather than silently drop |
| User loses `connectors:upload`                                        | all non-personal entries filtered out (`selectableConnectors` is already forced to `[]`)                                                                        |
| Connector's `objectPrefix` narrowed so a saved path is now outside it | filtered out, `unavailableReason: "path-not-allowed"`; the upload Lambda would 403 anyway                                                                       |
| Saved path empty                                                      | valid — means connector default; the existing prefix effect fills in `allowedPrefixes[0]`                                                                       |
| My Assets                                                             | one destination, no path dimension; saved as `path: ""`, labelled just "My Assets"; personal bucket and prefix never shown                                      |
| Stored My Assets path pointing at another user's folder               | filtered out, `unavailableReason: "path-not-allowed"`; the explorer and the upload handler both deny it server-side too                                         |
| User lacks `connectors:view`                                          | path browsing hidden for shared connectors (the explorer would 403); uploads still work to the default path                                                     |
| Two entries, same connector, different paths                          | both listed, distinct dropdown keys                                                                                                                             |
| Saved collection deleted or no longer addable                         | dropped from the request, warning shown, chip left visible                                                                                                      |
| Live collections not loaded yet                                       | nothing dropped                                                                                                                                                 |
| Cap reached (20)                                                      | star disabled with an explanatory tooltip; removal still works                                                                                                  |
| Connector renamed                                                     | stored `connectorName` is stale; display always re-resolves                                                                                                     |

## Tests

- `uploadLocation.types.test.ts` (24 cases) — normalisation, idempotence, dedup equality,
  label derivation, collection reconciliation (deleted / not-addable / archived / renamed /
  not-yet-loaded), and defensive parsing of unversioned and malformed payloads.
- `useUploadLocations.test.tsx` (22 cases) — availability filtering and reasons, My Assets as
  a target including sub-paths and rejection of another user's folder, save/remove/dedup, the
  cap, last-location write shape, and restore rejection when the connector is gone or the
  path is no longer allowed.
- `FileUploader.test.tsx` (+11 cases) — restore overriding My Assets, caller-pinned
  destinations winning (both `lockConnector` and explicit `path`), ignoring a dead remembered
  connector, the grouped dropdown sections, saving via the star, the saved-state label, My
  Assets never exposing its path or a browse affordance, My Assets saving with an empty path
  and a bare "My Assets" label (asserting the serialised entry contains no `personal/`), the
  empty path resolving back to `personal/{sub}/` for the actual upload, and browsing being
  hidden without `connectors:view`.
- `tests/unit/api/users/test_settings_put.py` (12 cases) — the size cap, the `#` guard, and
  the pre-existing contract.
- `tests/unit/api/connectors/test_s3_explorer_personal_access.py` (19 cases) — personal
  connector detection (including a `personal/` prefix without the `my-assets` type, a list of
  prefixes, and a leading slash), owner allowed, other users denied, unidentifiable caller
  denied, shared connectors unaffected, and sub extraction from both authorizer shapes.

## Verification

- `npx vitest run` (full suite): **105 files, 1048 tests, all pass** (was 103 / 991)
- `.venv/bin/pytest tests/unit`: my 31 new cases pass; **113 failures and 4 collection errors
  are pre-existing**, confirmed byte-identical against a stashed clean tree (a Powertools
  `Metrics` mocking incompatibility plus `upload_session_sweep`)
- `tsc --noEmit`: **0 errors**
- `npm run build`: succeeds
- ESLint: 0 errors (21 warnings, all pre-existing `no-explicit-any` in `FileUploader`'s Uppy
  callbacks)
- Not exercised against a live deployment.

One bug was caught by these tests and fixed during development: the new explorer helpers were
initially inserted between `lambda_handler`'s decorators and its `def`, which silently moved
`@logger.inject_lambda_context` / `@tracer.capture_lambda_handler` /
`@metrics.log_metrics` onto a helper and left the handler undecorated.

## Open questions

1. **Should a saved location pin an exact path, or a connector plus "whatever path I last
   used there"?** Implemented as an exact path — predictability wins for something you are
   writing bytes to — but the alternative survives prefix reorganisation better.

2. **Sub-paths inside My Assets** are deliberately not offered (see D6), so only the root is
   ever saved there. If they are wanted later, the display would need to hide the
   `personal/{sub}/` portion — that prefix is shared-infrastructure detail and showing a raw
   Cognito sub to a user is not acceptable.

3. **Group- or admin-level shared destinations?** `DashboardSelector` has a permission-gated
   "Save as Default for all users", so there is precedent. This would move storage off the
   per-user settings row, so it is worth knowing early if it is on the roadmap.

4. **Is 20 the right cap?**

5. **Should this eventually present as part of the existing "Favorites" family?** Assets,
   pipelines and collections share the `/users/favorites` API and a heart icon. A star was
   used here so the two concepts do not look interchangeable, but it is a visible
   inconsistency a reviewer may push back on.

6. **Server-side collection existence validation.** Currently client-side only, because
   presign is per file. If a stricter guarantee is wanted, the natural home is whatever
   downstream step consumes the `ml-collection-ids` directive, not the presign path.

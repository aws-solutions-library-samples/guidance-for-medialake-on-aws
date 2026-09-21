# Uppy 6 upgrade and Golden Retriever

Status: implemented on `refactor/uppy-upgrade` and verified end to end on ml-dev3 (see
"Deploy-time verification" at the bottom for what was run and what remains).

This document records why the Uppy 6 upgrade is a protocol change rather than a dependency
bump, the design chosen for MediaLake, and the work items. It is written for whoever reviews,
deploys, or later debugs browser uploads.

## Sources

- [Uppy 6.0 release post](https://uppy.io/blog/uppy-6.0/)
- [Migration guide, 5.x → 6.x](https://uppy.io/docs/guides/migration-guides/)
- [Rewriting @uppy/aws-s3 from scratch](https://uppy.io/blog/aws-s3-rewrite/)
- [@uppy/aws-s3 reference](https://uppy.io/docs/aws-s3/)
- [@uppy/golden-retriever reference](https://uppy.io/docs/golden-retriever/)
- Plugin source at `packages/@uppy/aws-s3/src` (`index.ts`, `S3Uploader.ts`,
  `s3-client/S3mini.ts`, `s3-client/S3Client.ts`) on `transloadit/uppy@main`, read to confirm
  which headers the browser actually sends.

## Versions

| Package                  | Before | After |
| ------------------------ | ------ | ----- |
| `@uppy/core`             | 5.2.0  | 6.0.1 |
| `@uppy/aws-s3`           | 5.1.0  | 6.1.0 |
| `@uppy/dashboard`        | 5.1.1  | 6.0.0 |
| `@uppy/react`            | 5.2.0  | 6.0.0 |
| `@uppy/golden-retriever` | —      | 6.0.0 |

Every plugin peer-depends on `@uppy/core ^6`, so the packages move together.

## What changed in Uppy 6 that matters here

Core, Dashboard and React are near no-ops for us: `@uppy/utils`, `@uppy/store-default`,
`@uppy/companion-client` and `@uppy/provider-views` were folded into `@uppy/core` subpaths,
and the `@uppy/react/dashboard` import still exists. We used none of the removed packages.

`@uppy/aws-s3` was rewritten:

1. The six per-operation callbacks we implemented (`getUploadParameters`,
   `createMultipartUpload`, `signPart`, `listParts`, `completeMultipartUpload`,
   `abortMultipartUpload`) are gone. There is one
   `signRequest({ method, key, uploadId?, partNumber? })` that returns `{ url, key? }`. The
   browser performs PutObject, CreateMultipartUpload, UploadPart, ListParts,
   CompleteMultipartUpload and AbortMultipartUpload itself against the presigned URLs.
2. Single-part uploads are a presigned **PUT**, not a presigned POST form. POST policy
   conditions (`content-length-range`, fixed `x-amz-meta-*` fields) no longer exist.
3. In the direct signing modes the browser sends the bytes plus one header, `Content-Type`
   (`file.type || 'application/octet-stream'` on PUT and CreateMultipartUpload,
   `application/xml` on CompleteMultipartUpload, none on UploadPart/ListParts/Abort). It never
   sends `x-amz-meta-*`; the client source carries a `// todo support metadata here too?`.
4. `signRequest` receives no file object. Anything the server needs to know about the file
   has to be carried by the client into the sign call.
5. The object key is proposed by the client (`generateObjectKey`). The server may replace it
   on the request that creates the object (PUT, or POST without `uploadId`) by returning
   `key`; every later request for that upload carries the server key and must be signed for
   exactly that key (aws-s3 ≥ 6.1.0).
6. Golden Retriever 6 keeps file metadata and Uppy state in IndexedDB (localStorage fallback
   chosen once at install), stores blobs ≤ 10 MiB in IndexedDB, and needs a service worker
   for larger blobs. Multipart resume after a refresh goes through the plugin's ListParts
   signing (`file.s3Multipart = { uploadId, key }` is persisted).

## Why this collides with MediaLake

MediaLake stamps upload _directives_ as S3 user metadata at upload time and reads them at
ingest:

- `POST /assets/upload` (`lambdas/api/assets/upload/post_upload`) stamps `ml-source=upload`,
  `ml-user-id`, and either `ml-collection-ids` or `ml-collection-overflow=1` (with the full
  list in the `UPLOADDIR#{bucket}#{key}` row of the upload-directives DynamoDB table).
- The portal (`lambdas/api/portal_public`) stamps `ml-source=upload-portal`, `ml-portal-id`,
  `ml-batch-id`, `ml-collection-ids` and `ml-usr-*` form fields.
- Both stamp them via presigned POST `Fields`/`Conditions` for single-part and via a
  server-side `create_multipart_upload(Metadata=…)` for multipart.
- The ingest Lambda (`lambdas/ingest/s3/index.py`) reads `head_object()["Metadata"]` and
  stores it at `Metadata.ObjectMetadata.S3.Metadata` on the asset record, which flows into
  DynamoDB, OpenSearch (via the table stream) and the `AssetCreated` event. Everything that
  consumes `ml-*` — Layer C collection association in ingest, `mark_upload_complete`,
  `mark_asset_failed`, `get_upload_session_metadata` — finds the keys by recursive search
  in that structure. None of them call S3.

With Uppy 6 the server never sees the CreateMultipartUpload or PutObject request, and the
browser sends no metadata, so nothing can stamp the object.

## Design

### Directives move to DynamoDB; ingest merges them

The upload-directives table already exists for the overflow case, keyed
`UPLOADDIR#{bucket}#{key}` with a TTL. It becomes the single carrier:

- The Lambda that _creates_ an upload (the sign call for PUT or for POST-without-`uploadId`)
  writes one row:

  ```json
  {
    "PK": "UPLOADDIR#<bucket>#<key>",
    "directives": { "ml-source": "upload", "ml-user-id": "…", "ml-collection-ids": "a,b" },
    "collectionIds": ["a", "b"],
    "userId": "…",
    "connectorId": "…",
    "expiresAt": <now + 7 days>
  }
  ```

  `directives` is exactly the map that used to be stamped as `x-amz-meta-*`, keys already
  lowercased. `collectionIds`/`userId` are kept so the existing overflow reader still works
  for objects created before the deploy. TTL grows from 24 h to 7 days because a Golden
  Retriever restore can resume a multipart upload well after the create call.

- Ingest, right after `head_object`, checks whether `response["Metadata"]` carries
  `ml-source`. If not, it reads `UPLOADDIR#{bucket}#{key}` and merges `directives` into
  `response["Metadata"]` before `_create_asset_metadata`. Object metadata wins over the row
  on key conflicts (objects stamped by the old client keep their behaviour). Because the
  merge happens before the asset record is built, every downstream consumer keeps working
  with no change.
- The 2 KB S3 metadata budget no longer applies, so the overflow marker is not written for
  new uploads. The reader path for `ml-collection-overflow=1` stays for in-flight objects.

### Presign contract

Assets API:

- `POST /assets/upload` — unchanged request body (`connector_id`, `filename`,
  `content_type`, `file_size`, `path`, `collection_ids`) plus `method: "PUT" | "POST"`, which
  is the method Uppy asked to sign. All existing validation (connector, allowed prefixes,
  personal-path ownership, `connectors:upload`, filename rules) is unchanged. The server
  builds the key as before and returns
  `{ bucket, key, url, method, multipart, expires_in }`. `PUT` is presigned with
  `ContentType` and `ContentLength=file_size` (`content-length` becomes a signed header, so
  the declared size is enforced exactly — a stricter replacement for the old
  `content-length-range`). `POST` is presigned `create_multipart_upload` with
  `ContentType`. The directive row is written here.
- `POST /assets/upload/multipart/sign` — body gains `operation: "part" | "list" |
"complete" | "abort"` (default `part`); `part_number` is required only for `part`. Returns
  `{ presigned_url, expires_in, operation, part_number? }`. Presigned with `host`-only
  signed headers, which matches what the browser sends.
- `POST /assets/upload/multipart/complete` and `/abort` are removed (the browser performs
  these operations against presigned URLs). Their Lambdas and routes are deleted from CDK.
- The custom authorizer maps `post /assets/upload/multipart/sign` to `assets:upload`
  explicitly; previously the multipart routes were unmapped and therefore allowed for any
  authenticated caller.

Portal API (`/portal/{slug}/…`): the same shape — `upload` gains `method`, returns
`{ multipart, sessionId, bucket, key, url, method }`; `upload/multipart/sign` gains
`operation`; `complete`/`abort` routes are removed. The portal's post-completion
`maxFileSizeBytes` HEAD-and-delete check cannot survive browser-side completion; single-part
size is enforced by the signed `content-length`, multipart total size is enforced client-side
only (see follow-ups).

### Client mapping to `signRequest`

`generateObjectKey` returns `file.id`. For the create request the client resolves the Uppy
file from `request.key`, calls the create endpoint with the file's name/type/size and the
current destination, and returns the server's `url` and `key`. It then stamps
`file.meta.s3Key`, `s3Bucket`, `s3ConnectorId` so that later requests (which arrive with the
server key and an `uploadId`) can be routed to the right connector by looking the file up by
key — including after a Golden Retriever restore, when in-memory maps are gone but file meta
is restored.

`content_type` sent to the server is `file.type || 'application/octet-stream'`, the same
expression the plugin uses for the `Content-Type` header, so the signed header always matches.

### Golden Retriever

`uppy.use(GoldenRetriever, { serviceWorker: true, expires: 7 days })` on both uploaders. The
service worker is a Vite entry (`sw.js` → `/sw.js`) importing
`@uppy/golden-retriever/lib/ServiceWorker.js`, registered once at app start with
`{ type: 'module' }`; registration failure is logged and non-fatal (browsers without module
service workers, notably Firefox, still get IndexedDB-based restore of state and small files).
Restored multipart uploads resume through ListParts; restored single-part files re-create the
upload; files whose blob could not be restored appear as ghosts in the Dashboard with the
built-in re-select prompt.

The service worker holds blobs in memory only, and Chromium terminates an idle worker after
about 30 seconds. Golden Retriever only messages the worker on file add/remove, so any upload
longer than that lost its blobs and a refresh produced ghosts (observed on ml-dev3 with a
114 MB file: blob present in the worker before upload, gone by the time part 1 landed).
`useServiceWorkerKeepalive` (used by both uploaders) sends a `uppy/GET_FILES` probe for an
unused store every 20 seconds while the Uppy instance holds files that have not finished
uploading, which keeps the worker — and the blobs — alive.

### CORS and IAM

- Connector buckets: the `medialake-upload-*` CORS rule written by `POST /connectors/s3`
  gains `DELETE` (abort) and the reconciler merges methods for existing rules. `GET`,
  `ETag` exposure and `Content-Type` are already present.
- Personal and media buckets in CDK already allow `GET, PUT, POST, DELETE, HEAD` and expose
  `ETag`.
- The sign Lambda role gains `s3:ListMultipartUploadParts` and `s3:AbortMultipartUpload`
  (S3 evaluates the signer's permissions when a presigned URL is used). `s3:PutObject` covers
  Create/UploadPart/Complete.
- The portal Lambda gains the directives table name and write access.

## What landed

| Area                                            | Change                                                                                                                                                                                                       | Verification                                                                               |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------ |
| `lambdas/api/assets/upload/post_upload`         | `method` field, presigned PUT (type + exact size signed) / CreateMultipartUpload, directive row with 7-day TTL, server key returned                                                                          | `tests/unit/api/upload/test_post_upload_persistence_moto.py` (moto, handler end to end)    |
| `lambdas/api/assets/upload/multipart_sign`      | `operation: part\|list\|complete\|abort`, HTTP method in response, refuses other users' `personal/` keys                                                                                                     | `tests/unit/api/upload/test_multipart_sign_operations.py`                                  |
| `multipart_complete`, `multipart_abort` Lambdas | Deleted with their routes and IAM                                                                                                                                                                            | `tests/unit/stacks/test_assets_upload_wiring.py`                                           |
| `lambdas/ingest/s3`                             | `merge_upload_directives` after `head_object`                                                                                                                                                                | `tests/unit/ingest/s3/test_upload_directives_merge.py`, round-trip property test           |
| `lambdas/api/portal_public`                     | Same protocol change; directive row carries `ml-source`, `ml-portal-id`, `ml-batch-id`, `ml-collection-ids`, `ml-usr-*`                                                                                      | `tests/unit/api/portal_public/test_hardening.py`, `test_upload_session_endpoints.py`       |
| CDK                                             | Sign Lambda gets ListParts/Abort; portal Lambda gets the directives table; complete/abort routes removed; authorizer maps the sign route to `assets:upload`                                                  | `tests/unit/stacks/test_assets_upload_wiring.py`, `test_portal_api_stack.py` (need Docker) |
| `lambdas/api/connectors/s3/post_s3`             | Connector CORS rule allows `DELETE`; reconciler tops up existing buckets                                                                                                                                     | `tests/unit/api/connectors/test_s3_cors_reconciliation.py`                                 |
| Frontend                                        | `@uppy/*` 6.x, `@uppy/golden-retriever`, `signRequest` in `FileUploader` and `PortalUploader`, shared helpers in `src/features/upload/utils/uppySignRequest.ts`, `sw.js` Vite entry registered in `main.tsx` | vitest (1233 tests), `tsc --noEmit`, `vite build`                                          |

The single-part `content-length` enforcement and the multipart `ListParts`/`Abort` paths are
exercised against real S3 only at deploy time; unit tests pin the signed headers and IAM.

## Follow-ups (not in this change)

- Portal multipart total-size enforcement moved to ingest (directive row could carry
  `maxFileSizeBytes`; ingest would delete oversize objects). Deliberately not added here
  because it introduces object deletion into ingest.
- Retire the `ml-collection-overflow` reader once no pre-deploy uploads can be in flight.
- Consider `@uppy/aws-s3` metadata support upstream (the S3 client has a TODO for it), which
  would allow stamping objects again and make the directive row a fallback.

## Deploy-time verification

Run on ml-dev3 (account 034362042487, 2026-09-21) against a fresh S3 connector
(`uppy-qa-media`) with a collection selected in the uploader:

| Check                                                      | Result                                                                                                                                                                                                                                           |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 124 KB `small.mp4` (single-part)                           | `POST /v1/assets/upload` → presigned `PUT` 200. Ingest log: "Applied upload directives from the directives table … ['ml-collection-ids', 'ml-source', 'ml-user-id']", asset created, "Added asset … to collection col_afae9d10 (source=upload)". |
| 114 MB `large.mov` (multipart, 3 × 50 MB parts)            | CreateMultipartUpload `POST ?uploads=` 200, 3 × sign + part `PUT` 200, Complete `POST ?uploadId=` 200; ingest and collection association as above. Directive rows present in `medialake-upload-directives-dev` with `expiresAt`.                 |
| Cancel single-part mid-upload                              | `PUT` aborted client-side; no object left in the bucket.                                                                                                                                                                                         |
| Cancel multipart mid-upload                                | `DELETE ?uploadId=` 204; `list-multipart-uploads` empty; existing object untouched.                                                                                                                                                              |
| Refresh mid-upload, 21 MB single-part                      | Dashboard: "We restored all files. You can now resume the upload." Resume issues a new presigned `PUT` and completes.                                                                                                                            |
| Refresh mid-upload, 114 MB multipart (after part 1 landed) | Before the keepalive fix: ghost, "Please re-select". After: full restore; resume shows sign(list) → `GET ?uploadId=` (ListParts) 200 → parts 2 and 3 only → Complete 200 under the original upload id; the completed object's ETag is `…-3`.     |

Not yet run: the portal upload path (needs a portal configured on the environment) and the
size-mismatch `PUT` → `SignatureDoesNotMatch` check. Both remain below for the next pass.

1. Portal: upload with a form that selects collections; confirm `ml-batch-id` reaches
   `mark_upload_complete` and the session completes.
2. Attempt a PUT whose body size differs from the declared `file_size`; confirm S3 rejects
   it with `SignatureDoesNotMatch`.

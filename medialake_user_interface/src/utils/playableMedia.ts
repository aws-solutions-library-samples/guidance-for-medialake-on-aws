/**
 * Resolving a playable media URL for an asset.
 *
 * ## Why this exists
 *
 * The asset detail page used to pick its player source like this:
 *
 * ```ts
 * proxyRep?.URL || asset.DigitalSourceAsset.MainRepresentation
 *   .StorageInfo.PrimaryLocation.ObjectKey.FullPath
 * ```
 *
 * The assets API only attaches a playable `URL` to *derived* representations —
 * proxy, thumbnail and smartcrop. The main representation never gets one. So when
 * no proxy existed yet the fallback handed the player a bare S3 object key
 * (`videos/clip.mp4`), which is not a URL, and the player failed on it. That is
 * the "invalid url" in place of the media reported in
 * https://github.com/aws-solutions-library-samples/guidance-for-medialake-on-aws/issues/27
 *
 * A proxy is produced asynchronously by a pipeline, so "no proxy yet" is a normal
 * transient state for a freshly ingested asset — not an error, and not something
 * to paper over with a value that cannot work. This returns `undefined` in that
 * case so callers can say so explicitly.
 */

/** An asset's derived representation, as far as this module cares. */
interface DerivedRepresentationLike {
  Purpose?: string;
  URL?: string;
}

/**
 * True for a value that a media element can actually load.
 *
 * Deliberately strict: the API builds these with CloudFront, so a playable URL is
 * always absolute `http(s)`. Anything else here — most importantly a bare S3
 * object key — is a bug upstream, and treating it as a source is what produced the
 * original defect.
 */
function isLoadableMediaUrl(value: unknown): value is string {
  if (typeof value !== "string") return false;

  const trimmed = value.trim();
  if (!trimmed) return false;

  try {
    const { protocol } = new URL(trimmed);
    return protocol === "http:" || protocol === "https:";
  } catch {
    // Not absolute — a relative path or object key.
    return false;
  }
}

/**
 * The URL to play for an asset, or `undefined` when there is nothing playable.
 *
 * Only the `proxy` representation is considered. Thumbnails are stills, and
 * smartcrops are reframed derivatives chosen explicitly through the Versions tab
 * rather than substituted in silently.
 */
export function resolvePlayableMediaUrl(asset: unknown): string | undefined {
  const reps = (asset as { DerivedRepresentations?: unknown })?.DerivedRepresentations;
  if (!Array.isArray(reps)) return undefined;

  const proxy = (reps as DerivedRepresentationLike[]).find(
    (rep) => rep?.Purpose === "proxy" && isLoadableMediaUrl(rep?.URL)
  );

  return proxy?.URL;
}

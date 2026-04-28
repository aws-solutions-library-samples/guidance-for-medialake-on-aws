/**
 * Resolve a dot-separated field path against an object, automatically
 * traversing into arrays when encountered at any intermediate level.
 *
 * Example: given path "Metadata.EmbeddedMetadata.video.r_frame_rate"
 * and an object where `video` is an array [{r_frame_rate:"24/1"}],
 * this returns ["24/1"].
 *
 * @returns A single primitive value, an array of collected values, or undefined.
 */
export function resolveDotPath(obj: unknown, path: string): unknown {
  if (!path || path.trim() === "") return obj;

  const keys = path.split(".");
  let current: unknown = obj;

  for (let i = 0; i < keys.length; i++) {
    if (current == null) return undefined;

    if (Array.isArray(current)) {
      // Collect the remaining path from every array element
      const remaining = keys.slice(i).join(".");
      const collected = current
        .map((item) => resolveDotPath(item, remaining))
        .flat()
        .filter((v) => v != null);
      return collected.length === 1 ? collected[0] : collected.length > 0 ? collected : undefined;
    }

    current = (current as Record<string, unknown>)[keys[i]];
  }

  return current;
}

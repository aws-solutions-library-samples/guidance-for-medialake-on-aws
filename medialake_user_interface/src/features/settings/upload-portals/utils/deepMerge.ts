/**
 * Type guard for plain objects (objects created via `{}` or `Object.create(null)`).
 *
 * Returns `true` only when the prototype is `Object.prototype` or `null`. This
 * deliberately excludes arrays, `Date`s, class instances, `Map`/`Set`, and all
 * other non-plain objects so that {@link deepMerge} treats them as leaves.
 */
export function isPlainObject(v: unknown): v is Record<string, unknown> {
  if (v === null || typeof v !== "object") {
    return false;
  }
  const proto = Object.getPrototypeOf(v);
  return proto === Object.prototype || proto === null;
}

/**
 * Deep-merge `source` into `target`, producing a NEW object.
 *
 * Contract:
 * - Never mutates `target` or `source`.
 * - For every key `k` in `target`:
 *   - If `source[k] === undefined` -> result[k] === target[k]
 *   - Else if both values are plain objects -> result[k] === deepMerge(target[k], source[k])
 *   - Else -> result[k] === source[k]
 * - For every key `k` only in `source` (and not `undefined`) -> result[k] === source[k]
 * - Arrays and primitive leaves are overwritten wholesale (no element-wise merging).
 * - Only plain objects (see {@link isPlainObject}) trigger recursion. `null`,
 *   arrays, `Date`s, class instances, functions, and primitives are all leaves.
 *
 * Structural sharing of untouched subtrees is acceptable — the result is a new
 * object but nested subtrees that were not rewritten may be referentially
 * shared with `target`.
 */
export function deepMerge<T extends Record<string, unknown>>(target: T, source: Partial<T>): T {
  const result: Record<string, unknown> = { ...target };

  for (const key of Object.keys(source) as Array<keyof T & string>) {
    const sourceValue = source[key];

    if (sourceValue === undefined) {
      // Explicit: undefined on source means "keep target".
      continue;
    }

    const targetValue = (target as Record<string, unknown>)[key];

    if (isPlainObject(targetValue) && isPlainObject(sourceValue)) {
      result[key] = deepMerge(targetValue, sourceValue as Partial<typeof targetValue>);
    } else {
      result[key] = sourceValue;
    }
  }

  return result as T;
}

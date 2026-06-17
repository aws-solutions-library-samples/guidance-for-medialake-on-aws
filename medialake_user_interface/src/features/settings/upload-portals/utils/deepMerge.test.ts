import { describe, expect, it } from "vitest";
import { deepMerge, isPlainObject } from "./deepMerge";

describe("isPlainObject", () => {
  it("returns true for object literals", () => {
    expect(isPlainObject({})).toBe(true);
    expect(isPlainObject({ a: 1 })).toBe(true);
  });

  it("returns true for Object.create(null)", () => {
    expect(isPlainObject(Object.create(null))).toBe(true);
  });

  it("returns false for null and primitives", () => {
    expect(isPlainObject(null)).toBe(false);
    expect(isPlainObject(undefined)).toBe(false);
    expect(isPlainObject(0)).toBe(false);
    expect(isPlainObject("hello")).toBe(false);
    expect(isPlainObject(true)).toBe(false);
  });

  it("returns false for arrays", () => {
    expect(isPlainObject([])).toBe(false);
    expect(isPlainObject([1, 2, 3])).toBe(false);
  });

  it("returns false for Dates", () => {
    expect(isPlainObject(new Date())).toBe(false);
  });

  it("returns false for class instances", () => {
    class Foo {}
    expect(isPlainObject(new Foo())).toBe(false);
  });

  it("returns false for functions", () => {
    expect(isPlainObject(() => 0)).toBe(false);
    expect(isPlainObject(function named() {})).toBe(false);
  });
});

describe("deepMerge", () => {
  it("does not mutate target or source", () => {
    type Shape = { a: number; nested: { b: number; c: number } };
    const target: Shape = { a: 1, nested: { b: 2, c: 3 } };
    // Source is a runtime-partial nested override ({ nested: { c } } without
    // b). The `deepMerge` type signature is `Partial<T>` (shallow-partial), so
    // we cast to express the deeper-partial intent the implementation supports
    // at runtime.
    const source = { nested: { c: 99 } } as unknown as Partial<Shape>;
    const targetSnapshot = structuredClone(target);
    const sourceSnapshot = structuredClone(source);

    const result = deepMerge(target, source);

    expect(target).toEqual(targetSnapshot);
    expect(source).toEqual(sourceSnapshot);
    expect(result.nested).toEqual({ b: 2, c: 99 });
  });

  it("treats source[k] === undefined as 'keep target'", () => {
    const result = deepMerge({ a: 1 }, { a: undefined } as unknown as Partial<{ a: number }>);
    expect(result.a).toBe(1);
  });

  it("applies nested partial overrides without discarding sibling keys", () => {
    type Shape = { a: { b: number; c: number } };
    const result = deepMerge<Shape>({ a: { b: 1, c: 2 } }, {
      a: { c: 5 },
    } as unknown as Partial<Shape>);
    expect(result.a).toEqual({ b: 1, c: 5 });
  });

  it("overwrites arrays wholesale (no element-wise merging)", () => {
    const result = deepMerge({ a: [1, 2, 3] }, { a: [9] });
    expect(result.a).toEqual([9]);
  });

  it("overwrites primitive leaves", () => {
    expect(deepMerge({ a: 1 }, { a: 2 }).a).toBe(2);
    expect(deepMerge({ a: "old" }, { a: "new" }).a).toBe("new");
    expect(deepMerge({ a: true }, { a: false }).a).toBe(false);
  });

  it("deepMerge(defaults, {}) is deep-equal to defaults", () => {
    const defaults = {
      colors: { primary: "#000", secondary: "#fff" },
      layout: { width: 680, radius: 12 },
    };

    const result = deepMerge(defaults, {});

    expect(result).toEqual(defaults);
  });

  it("does not recurse into Date instances — they are overwritten wholesale", () => {
    const oldDate = new Date("2020-01-01T00:00:00Z");
    const newDate = new Date("2024-06-15T12:00:00Z");

    const result = deepMerge<{ a: Date }>({ a: oldDate }, { a: newDate });

    expect(result.a).toBe(newDate);
    expect(result.a).not.toBe(oldDate);
  });

  it("does not recurse into class instances — they are overwritten wholesale", () => {
    class Wrapper {
      constructor(public label: string) {}
    }

    const oldInstance = new Wrapper("old");
    const newInstance = new Wrapper("new");

    const result = deepMerge<{ w: Wrapper }>({ w: oldInstance }, { w: newInstance });

    expect(result.w).toBe(newInstance);
  });

  it("keeps keys only in target when source omits them", () => {
    const result = deepMerge({ a: 1, b: 2 }, { a: 10 } as unknown as Partial<{
      a: number;
      b: number;
    }>);
    expect(result).toEqual({ a: 10, b: 2 });
  });

  it("adds keys only present in source", () => {
    const result = deepMerge(
      { a: 1 } as Record<string, unknown>,
      { b: 2 } as Record<string, unknown>
    );
    expect(result).toEqual({ a: 1, b: 2 });
  });

  it("distinguishes null from undefined — null overwrites target", () => {
    const result = deepMerge(
      { a: 1 } as { a: number | null },
      { a: null } as Partial<{ a: number | null }>
    );
    expect(result.a).toBeNull();
  });

  it("replaces an object leaf with a non-object leaf", () => {
    const result = deepMerge<{ a: { b: number } | string }>({ a: { b: 1 } }, { a: "now a string" });
    expect(result.a).toBe("now a string");
  });

  it("replaces a non-object leaf with an object", () => {
    const result = deepMerge<{ a: number | { b: number } }>({ a: 1 }, { a: { b: 2 } });
    expect(result.a).toEqual({ b: 2 });
  });

  it("merges deeply-nested structures", () => {
    type Shape = {
      l1: {
        l2: {
          l3: { keep: string; override: string };
          sibling: number;
        };
      };
    };
    const target: Shape = {
      l1: {
        l2: {
          l3: { keep: "me", override: "old" },
          sibling: 1,
        },
      },
    };
    const source = {
      l1: {
        l2: {
          l3: { override: "new" },
        },
      },
    } as unknown as Partial<Shape>;

    const result = deepMerge(target, source);

    expect(result).toEqual({
      l1: {
        l2: {
          l3: { keep: "me", override: "new" },
          sibling: 1,
        },
      },
    });
  });

  it("returns a new top-level object (not reference-equal to target)", () => {
    const defaults = { a: 1 };
    const result = deepMerge(defaults, {});
    expect(result).toEqual(defaults);
    expect(result).not.toBe(defaults);
  });
});

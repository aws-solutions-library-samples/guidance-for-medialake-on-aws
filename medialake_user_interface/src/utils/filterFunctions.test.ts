import { describe, it, expect } from "vitest";
import { includesString } from "./filterFunctions";

// Minimal row mock matching TanStack Table's Row interface
function makeRow(columnId: string, value: unknown) {
  return {
    getValue: (id: string) => (id === columnId ? value : undefined),
  } as any;
}

describe("includesString", () => {
  it("returns true when value contains filter string", () => {
    expect(includesString(makeRow("name", "Hello World"), "name", "hello", () => {})).toBe(true);
  });

  it("is case-insensitive", () => {
    expect(includesString(makeRow("name", "HELLO"), "name", "hello", () => {})).toBe(true);
  });

  it("returns false when value does not contain filter string", () => {
    expect(includesString(makeRow("name", "Hello"), "name", "xyz", () => {})).toBe(false);
  });

  it("returns false for null/undefined values", () => {
    expect(includesString(makeRow("name", null), "name", "test", () => {})).toBe(false);
    expect(includesString(makeRow("name", undefined), "name", "test", () => {})).toBe(false);
  });

  it("handles numeric values by converting to string", () => {
    expect(includesString(makeRow("size", 12345), "size", "234", () => {})).toBe(true);
  });
});

import { describe, it, expect } from "vitest";
import { formatCamelCase } from "./stringUtils";

describe("formatCamelCase", () => {
  it("inserts space before uppercase letters", () => {
    expect(formatCamelCase("camelCase")).toBe("Camel Case");
  });

  it("capitalizes the first letter", () => {
    expect(formatCamelCase("hello")).toBe("Hello");
  });

  it("handles already capitalized input", () => {
    expect(formatCamelCase("Hello")).toBe("Hello");
  });

  it("handles multiple camelCase transitions", () => {
    expect(formatCamelCase("myLongVariableName")).toBe("My Long Variable Name");
  });

  it("handles single character", () => {
    expect(formatCamelCase("a")).toBe("A");
  });

  it("handles empty string", () => {
    expect(formatCamelCase("")).toBe("");
  });
});

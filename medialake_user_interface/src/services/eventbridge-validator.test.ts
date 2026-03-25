import { describe, it, expect } from "vitest";
import { EventBridgePatternValidator } from "./eventbridge-validator";

describe("EventBridgePatternValidator", () => {
  describe("basic validation", () => {
    it("rejects non-object patterns", () => {
      const result = EventBridgePatternValidator.validate(null as any);
      expect(result.valid).toBe(false);
      expect(result.errors[0].message).toContain("valid JSON object");
    });

    it("accepts a valid minimal pattern", () => {
      const result = EventBridgePatternValidator.validate({ source: ["my.app"] });
      expect(result.valid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    it("rejects invalid root fields", () => {
      const result = EventBridgePatternValidator.validate({ badField: ["value"] });
      expect(result.valid).toBe(false);
      expect(result.errors[0].message).toContain("Invalid root field");
    });

    it("accepts all valid root fields", () => {
      const result = EventBridgePatternValidator.validate({
        source: ["a"],
        "detail-type": ["b"],
        detail: {},
        account: ["123"],
        region: ["us-east-1"],
        time: ["2025-01-01"],
        id: ["abc"],
        resources: ["arn:aws:s3:::bucket"],
      });
      expect(result.valid).toBe(true);
    });

    it("rejects oversized patterns", () => {
      const bigValue = "x".repeat(2100);
      const result = EventBridgePatternValidator.validate({ source: [bigValue] });
      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.message.includes("exceeds"))).toBe(true);
    });
  });

  describe("numeric operator", () => {
    it("validates correct numeric patterns", () => {
      const result = EventBridgePatternValidator.validate({
        detail: { price: [{ numeric: [">", 100, "<=", 500] }] },
      });
      expect(result.valid).toBe(true);
    });

    it("rejects non-array numeric value", () => {
      const result = EventBridgePatternValidator.validate({
        detail: { price: [{ numeric: "bad" }] },
      });
      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.message.includes("must be an array"))).toBe(true);
    });

    it("rejects invalid numeric operators", () => {
      const result = EventBridgePatternValidator.validate({
        detail: { price: [{ numeric: ["~", 5] }] },
      });
      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.message.includes("Invalid numeric operator"))).toBe(true);
    });

    it("rejects missing numeric value after operator", () => {
      const result = EventBridgePatternValidator.validate({
        detail: { price: [{ numeric: [">"] }] },
      });
      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.message.includes("missing value"))).toBe(true);
    });

    it("rejects non-number values", () => {
      const result = EventBridgePatternValidator.validate({
        detail: { price: [{ numeric: [">", "five"] }] },
      });
      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.message.includes("must be a number"))).toBe(true);
    });

    it("rejects out-of-range numeric values", () => {
      const result = EventBridgePatternValidator.validate({
        detail: { price: [{ numeric: [">", 6e9] }] },
      });
      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.message.includes("out of range"))).toBe(true);
    });
  });

  describe("CIDR operator", () => {
    it("accepts valid IPv4 CIDR", () => {
      const result = EventBridgePatternValidator.validate({
        detail: { ip: [{ cidr: "10.0.0.0/24" }] },
      });
      expect(result.valid).toBe(true);
    });

    it("rejects non-string CIDR", () => {
      const result = EventBridgePatternValidator.validate({
        detail: { ip: [{ cidr: 123 }] },
      });
      expect(result.valid).toBe(false);
    });

    it("rejects invalid CIDR format", () => {
      const result = EventBridgePatternValidator.validate({
        detail: { ip: [{ cidr: "not-a-cidr" }] },
      });
      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.message.includes("Invalid CIDR"))).toBe(true);
    });
  });

  describe("exists operator", () => {
    it("accepts boolean true", () => {
      const result = EventBridgePatternValidator.validate({
        detail: { field: [{ exists: true }] },
      });
      expect(result.valid).toBe(true);
    });

    it("accepts boolean false", () => {
      const result = EventBridgePatternValidator.validate({
        detail: { field: [{ exists: false }] },
      });
      expect(result.valid).toBe(true);
    });

    it("rejects non-boolean exists", () => {
      const result = EventBridgePatternValidator.validate({
        detail: { field: [{ exists: "yes" }] },
      });
      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.message.includes("true or false"))).toBe(true);
    });
  });

  describe("wildcard operator", () => {
    it("accepts valid wildcard string", () => {
      const result = EventBridgePatternValidator.validate({
        detail: { name: [{ wildcard: "foo*bar" }] },
      });
      expect(result.valid).toBe(true);
    });

    it("rejects consecutive wildcards", () => {
      const result = EventBridgePatternValidator.validate({
        detail: { name: [{ wildcard: "foo**bar" }] },
      });
      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.message.includes("Consecutive"))).toBe(true);
    });

    it("warns on many wildcards", () => {
      const result = EventBridgePatternValidator.validate({
        detail: { name: [{ wildcard: "*a*b*c*d*" }] },
      });
      // 5 wildcards > 3 threshold
      expect(result.warnings.some((w) => w.message.includes("complexity"))).toBe(true);
    });

    it("rejects non-string/non-array wildcard", () => {
      const result = EventBridgePatternValidator.validate({
        detail: { name: [{ wildcard: 123 }] },
      });
      expect(result.valid).toBe(false);
    });

    it("validates wildcard arrays", () => {
      const result = EventBridgePatternValidator.validate({
        detail: { name: [{ wildcard: ["foo*", "bar*"] }] },
      });
      expect(result.valid).toBe(true);
    });
  });

  describe("unknown operators", () => {
    it("rejects unknown operators", () => {
      const result = EventBridgePatternValidator.validate({
        detail: { field: [{ badOp: "value" }] },
      });
      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.message.includes("Unknown operator"))).toBe(true);
    });
  });

  describe("$or operator", () => {
    it("accepts valid $or", () => {
      const result = EventBridgePatternValidator.validate({
        detail: { $or: [{ status: ["active"] }, { status: ["pending"] }] },
      });
      expect(result.valid).toBe(true);
    });

    it("rejects non-array $or", () => {
      const result = EventBridgePatternValidator.validate({
        detail: { $or: "bad" },
      });
      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.message.includes("must be an array"))).toBe(true);
    });

    it("rejects empty $or", () => {
      const result = EventBridgePatternValidator.validate({
        detail: { $or: [] },
      });
      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.message.includes("cannot be empty"))).toBe(true);
    });
  });
});

import { describe, it, expect } from "vitest";
import {
  environmentFormSchema,
  defaultEnvironmentFormData,
  EnvironmentStatusValues,
} from "./environmentFormSchema";

describe("environmentFormSchema", () => {
  it("accepts valid form data", () => {
    const result = environmentFormSchema.safeParse({
      name: "Production",
      region: "us-east-1",
      status: "active",
      tags: { "cost-center": "CC-123", team: "platform" },
    });
    expect(result.success).toBe(true);
  });

  it("rejects empty name", () => {
    const result = environmentFormSchema.safeParse({
      ...defaultEnvironmentFormData,
      name: "",
    });
    expect(result.success).toBe(false);
  });

  it("rejects empty region", () => {
    const result = environmentFormSchema.safeParse({
      ...defaultEnvironmentFormData,
      region: "",
    });
    expect(result.success).toBe(false);
  });

  it("rejects invalid status", () => {
    const result = environmentFormSchema.safeParse({
      ...defaultEnvironmentFormData,
      name: "Test",
      status: "invalid",
    });
    expect(result.success).toBe(false);
  });

  it("accepts active status", () => {
    const result = environmentFormSchema.safeParse({
      name: "Test",
      region: "us-west-2",
      status: EnvironmentStatusValues.Active,
      tags: { "cost-center": "CC-1", team: "dev" },
    });
    expect(result.success).toBe(true);
  });

  it("accepts disabled status", () => {
    const result = environmentFormSchema.safeParse({
      name: "Test",
      region: "us-west-2",
      status: EnvironmentStatusValues.Disabled,
      tags: { "cost-center": "CC-1", team: "dev" },
    });
    expect(result.success).toBe(true);
  });

  it("rejects missing cost-center tag", () => {
    const result = environmentFormSchema.safeParse({
      name: "Test",
      region: "us-west-2",
      status: "active",
      tags: { "cost-center": "", team: "dev" },
    });
    expect(result.success).toBe(false);
  });

  it("rejects missing team tag", () => {
    const result = environmentFormSchema.safeParse({
      name: "Test",
      region: "us-west-2",
      status: "active",
      tags: { "cost-center": "CC-1", team: "" },
    });
    expect(result.success).toBe(false);
  });

  it("allows additional tags beyond required ones", () => {
    const result = environmentFormSchema.safeParse({
      name: "Test",
      region: "us-west-2",
      status: "active",
      tags: { "cost-center": "CC-1", team: "dev", environment: "staging" },
    });
    expect(result.success).toBe(true);
  });
});

describe("defaultEnvironmentFormData", () => {
  it("has expected defaults", () => {
    expect(defaultEnvironmentFormData.name).toBe("");
    expect(defaultEnvironmentFormData.region).toBe("us-west-2");
    expect(defaultEnvironmentFormData.status).toBe("active");
  });
});

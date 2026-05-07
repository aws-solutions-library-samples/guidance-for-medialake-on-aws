import { describe, it, expect } from "vitest";
import { integrationFormSchema, createIntegrationFormDefaults } from "./integrationFormSchema";

describe("integrationFormSchema", () => {
  it("accepts valid form data", () => {
    const result = integrationFormSchema.safeParse({
      nodeId: "node-1",
      environmentId: "env-1",
      description: "Test integration",
      auth: { type: "apiKey", credentials: { key: "abc123" } },
    });
    expect(result.success).toBe(true);
  });

  it("rejects empty nodeId", () => {
    const result = integrationFormSchema.safeParse({
      nodeId: "",
      environmentId: "env-1",
      description: "Test",
      auth: { type: "apiKey", credentials: {} },
    });
    expect(result.success).toBe(false);
  });

  it("rejects empty environmentId", () => {
    const result = integrationFormSchema.safeParse({
      nodeId: "node-1",
      environmentId: "",
      description: "Test",
      auth: { type: "apiKey", credentials: {} },
    });
    expect(result.success).toBe(false);
  });

  it("rejects empty description", () => {
    const result = integrationFormSchema.safeParse({
      nodeId: "node-1",
      environmentId: "env-1",
      description: "",
      auth: { type: "apiKey", credentials: {} },
    });
    expect(result.success).toBe(false);
  });

  it("accepts awsIam auth type", () => {
    const result = integrationFormSchema.safeParse({
      nodeId: "node-1",
      environmentId: "env-1",
      description: "Test",
      auth: { type: "awsIam", credentials: { roleArn: "arn:aws:iam::123456789012:role/MyRole" } },
    });
    expect(result.success).toBe(true);
  });

  it("rejects invalid auth type", () => {
    const result = integrationFormSchema.safeParse({
      nodeId: "node-1",
      environmentId: "env-1",
      description: "Test",
      auth: { type: "oauth", credentials: {} },
    });
    expect(result.success).toBe(false);
  });
});

describe("createIntegrationFormDefaults", () => {
  it("has expected defaults", () => {
    expect(createIntegrationFormDefaults.nodeId).toBe("");
    expect(createIntegrationFormDefaults.environmentId).toBe("");
    expect(createIntegrationFormDefaults.description).toBe("");
    expect(createIntegrationFormDefaults.auth.type).toBe("apiKey");
    expect(createIntegrationFormDefaults.auth.credentials).toEqual({});
  });
});

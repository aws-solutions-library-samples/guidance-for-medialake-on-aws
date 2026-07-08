import { describe, it, expect } from "vitest";
import { createZodSchema } from "./createZodSchema";
import type { FormFieldDefinition } from "../types";

describe("createZodSchema", () => {
  it("creates a schema for text fields", () => {
    const fields: FormFieldDefinition[] = [
      { name: "username", type: "text", label: "Username", required: true },
    ];
    const schema = createZodSchema(fields);
    const result = schema.safeParse({ username: "john" });
    expect(result.success).toBe(true);
  });

  it("creates a schema for number fields", () => {
    const fields: FormFieldDefinition[] = [
      { name: "count", type: "number", label: "Count", required: true },
    ];
    const schema = createZodSchema(fields);
    const result = schema.safeParse({ count: 5 });
    expect(result.success).toBe(true);
  });

  it("creates a schema for switch (boolean) fields", () => {
    const fields: FormFieldDefinition[] = [{ name: "enabled", type: "switch", label: "Enabled" }];
    const schema = createZodSchema(fields);
    const result = schema.safeParse({ enabled: true });
    expect(result.success).toBe(true);
  });

  it("creates a schema for select fields with options", () => {
    const fields: FormFieldDefinition[] = [
      {
        name: "role",
        type: "select",
        label: "Role",
        options: [
          { value: "admin", label: "Admin" },
          { value: "user", label: "User" },
        ],
      },
    ];
    const schema = createZodSchema(fields);
    const result = schema.safeParse({ role: "admin" });
    expect(result.success).toBe(true);
  });

  it("creates a schema for multiselect fields", () => {
    const fields: FormFieldDefinition[] = [
      {
        name: "tags",
        type: "multiselect",
        label: "Tags",
        options: [{ value: "a", label: "A" }],
      },
    ];
    const schema = createZodSchema(fields);
    const result = schema.safeParse({ tags: ["a"] });
    expect(result.success).toBe(true);
  });

  it("handles parameters.* prefixed fields", () => {
    const fields: FormFieldDefinition[] = [
      { name: "parameters.host", type: "text", label: "Host" },
      { name: "parameters.port", type: "number", label: "Port" },
    ];
    const schema = createZodSchema(fields);
    const result = schema.safeParse({ parameters: { host: "localhost", port: 8080 } });
    expect(result.success).toBe(true);
  });

  it("caches schemas for the same fields reference", () => {
    const fields: FormFieldDefinition[] = [{ name: "x", type: "text", label: "X" }];
    const schema1 = createZodSchema(fields);
    const schema2 = createZodSchema(fields);
    expect(schema1).toBe(schema2);
  });

  it("allows optional fields to be undefined", () => {
    const fields: FormFieldDefinition[] = [
      { name: "bio", type: "text", label: "Bio", required: false },
    ];
    const schema = createZodSchema(fields);
    const result = schema.safeParse({});
    expect(result.success).toBe(true);
  });

  it("allows an optional select field to be left unselected (empty string)", () => {
    // Regression test: a not-yet-selected MUI Select bound to a string sits
    // at "" (not undefined) until the user picks a value. An optional select
    // must accept that natural empty state instead of enforcing its enum.
    const fields: FormFieldDefinition[] = [
      {
        name: "parameters.portal_id",
        type: "select",
        label: "Portal (optional)",
        required: false,
        options: [{ value: "abc-123", label: "My Portal" }],
      },
    ];
    const schema = createZodSchema(fields);
    const result = schema.safeParse({ parameters: { portal_id: "" } });
    expect(result.success).toBe(true);
  });

  it("still rejects an optional select field given a value outside its options", () => {
    const fields: FormFieldDefinition[] = [
      {
        name: "parameters.portal_id",
        type: "select",
        label: "Portal (optional)",
        required: false,
        options: [{ value: "abc-123", label: "My Portal" }],
      },
    ];
    const schema = createZodSchema(fields);
    const result = schema.safeParse({ parameters: { portal_id: "not-a-real-id" } });
    expect(result.success).toBe(false);
  });

  it("still accepts a valid selected value for an optional select field", () => {
    const fields: FormFieldDefinition[] = [
      {
        name: "parameters.portal_id",
        type: "select",
        label: "Portal (optional)",
        required: false,
        options: [{ value: "abc-123", label: "My Portal" }],
      },
    ];
    const schema = createZodSchema(fields);
    const result = schema.safeParse({ parameters: { portal_id: "abc-123" } });
    expect(result.success).toBe(true);
  });
});

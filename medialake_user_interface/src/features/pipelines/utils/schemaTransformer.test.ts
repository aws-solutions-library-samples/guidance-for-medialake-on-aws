import { describe, it, expect } from "vitest";
import {
  transformParameterSchema,
  transformParametersArray,
  transformParametersRecordToArray,
  transformObjectParameter,
  normalizeParameter,
} from "./schemaTransformer";

describe("transformParameterSchema", () => {
  it("normalizes string type to text", () => {
    const param = { name: "prompt", schema: { type: "string" } };
    const result = transformParameterSchema(param);
    expect(result.schema.type).toBe("text");
  });

  it("normalizes integer type to number", () => {
    const param = { name: "count", schema: { type: "integer" } };
    const result = transformParameterSchema(param);
    expect(result.schema.type).toBe("number");
  });

  it("preserves multiline and rows in schema", () => {
    const param = {
      name: "prompt",
      schema: { type: "string", multiline: true, rows: 6 },
    };
    const result = transformParameterSchema(param);
    expect(result.schema.multiline).toBe(true);
    expect(result.schema.rows).toBe(6);
    expect(result.schema.type).toBe("text");
  });

  it("uses select type when options are present", () => {
    const param = {
      name: "model",
      schema: {
        type: "string",
        options: [{ value: "a", label: "A" }],
      },
    };
    const result = transformParameterSchema(param);
    expect(result.schema.type).toBe("select");
  });

  it("preserves defaultValue from param level", () => {
    const param = { name: "x", defaultValue: "hello", schema: { type: "string" } };
    expect(transformParameterSchema(param).defaultValue).toBe("hello");
  });

  it("preserves defaultValue from schema.default", () => {
    const param = { name: "x", schema: { type: "string", default: "world" } };
    expect(transformParameterSchema(param).defaultValue).toBe("world");
  });

  it("preserves showWhen", () => {
    const param = { name: "x", showWhen: { field: "y", value: true }, schema: { type: "string" } };
    expect(transformParameterSchema(param).showWhen).toEqual({ field: "y", value: true });
  });

  it("preserves placeholder", () => {
    const param = { name: "x", placeholder: "Enter...", schema: { type: "string" } };
    expect(transformParameterSchema(param).placeholder).toBe("Enter...");
  });

  it("handles legacy format with type at param level", () => {
    const param = { name: "x", type: "string", multiline: true, rows: 4 };
    const result = transformParameterSchema(param);
    expect(result.schema.type).toBe("text");
    expect(result.schema.multiline).toBe(true);
    expect(result.schema.rows).toBe(4);
  });

  it("copies options to parameter level from schema", () => {
    const opts = [{ value: "a", label: "A" }];
    const param = { name: "x", schema: { type: "string", options: opts } };
    expect(transformParameterSchema(param).options).toEqual(opts);
  });

  it("copies options from param level to schema", () => {
    const opts = [{ value: "b", label: "B" }];
    const param = { name: "x", options: opts, schema: { type: "string" } };
    const result = transformParameterSchema(param);
    expect(result.options).toEqual(opts);
    expect(result.schema.options).toEqual(opts);
  });

  it("uses name as label fallback", () => {
    const param = { name: "myField", schema: { type: "string" } };
    expect(transformParameterSchema(param).label).toBe("myField");
  });
});

describe("transformParametersArray", () => {
  it("transforms an array of parameters", () => {
    const params = [
      { name: "a", schema: { type: "string" } },
      { name: "b", schema: { type: "integer" } },
    ];
    const result = transformParametersArray(params);
    expect(result).toHaveLength(2);
    expect(result[0].schema.type).toBe("text");
    expect(result[1].schema.type).toBe("number");
  });

  it("returns empty array for non-array input", () => {
    expect(transformParametersArray("bad" as any)).toEqual([]);
  });
});

describe("transformParametersRecordToArray", () => {
  it("converts record to array", () => {
    const params = {
      prompt: { schema: { type: "string" } },
      count: { name: "count", schema: { type: "integer" } },
    };
    const result = transformParametersRecordToArray(params);
    expect(result).toHaveLength(2);
    expect(result[0].name).toBe("prompt");
    expect(result[1].name).toBe("count");
  });

  it("returns empty array for non-object input", () => {
    expect(transformParametersRecordToArray(null as any)).toEqual([]);
  });
});

describe("transformObjectParameter", () => {
  it("flattens object properties", () => {
    const param = {
      name: "config",
      schema: {
        properties: {
          host: { type: "string", description: "Hostname" },
          port: { type: "integer", default: 8080 },
        },
        required: ["host"],
      },
    };
    const result = transformObjectParameter(param);
    expect(result).toHaveLength(2);
    expect(result[0].name).toBe("host");
    expect(result[0].required).toBe(true);
    expect(result[0].schema.type).toBe("text");
    expect(result[1].name).toBe("port");
    expect(result[1].required).toBe(false);
    expect(result[1].schema.type).toBe("number");
  });

  it("returns empty array when no properties", () => {
    expect(transformObjectParameter({ name: "x", schema: {} })).toEqual([]);
  });
});

describe("normalizeParameter", () => {
  it("ensures schema exists", () => {
    const param = { name: "x" };
    const result = normalizeParameter(param);
    expect(result.schema).toBeDefined();
    expect(result.schema.type).toBe("text");
  });

  it("normalizes types", () => {
    const param = { name: "x", schema: { type: "integer" } };
    expect(normalizeParameter(param).schema.type).toBe("number");
  });
});

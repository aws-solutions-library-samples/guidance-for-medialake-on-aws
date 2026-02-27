import { describe, it, expect } from "vitest";
import {
  isValidApiKey,
  isStringBody,
  isNestedBodyData,
  isDirectData,
  parseApiKeysList,
  parseApiKey,
  parseStringBodyResponse,
  handleApiKeysError,
} from "./responseParser";

const validApiKey = {
  id: "key-1",
  name: "Test Key",
  description: "A test key",
  createdAt: "2025-01-01T00:00:00Z",
  updatedAt: "2025-01-01T00:00:00Z",
  isEnabled: true,
  lastUsed: null,
};

describe("isValidApiKey", () => {
  it("returns true for a valid API key", () => {
    expect(isValidApiKey(validApiKey)).toBe(true);
  });

  it("returns falsy for null", () => {
    expect(isValidApiKey(null)).toBeFalsy();
  });

  it("returns false when id is missing", () => {
    expect(isValidApiKey({ ...validApiKey, id: undefined })).toBe(false);
  });

  it("returns false when isEnabled is not boolean", () => {
    expect(isValidApiKey({ ...validApiKey, isEnabled: "yes" })).toBe(false);
  });

  it("accepts undefined description", () => {
    expect(isValidApiKey({ ...validApiKey, description: undefined })).toBe(true);
  });

  it("accepts null description", () => {
    expect(isValidApiKey({ ...validApiKey, description: null })).toBe(true);
  });
});

describe("type guards", () => {
  it("isStringBody detects string body", () => {
    expect(isStringBody({ body: '{"data":{}}' })).toBe(true);
    expect(isStringBody({ body: {} })).toBe(false);
    expect(isStringBody(null)).toBeFalsy();
  });

  it("isNestedBodyData detects nested body.data", () => {
    expect(isNestedBodyData({ body: { data: [] } })).toBe(true);
    expect(isNestedBodyData({ body: "string" })).toBe(false);
  });

  it("isDirectData detects direct data format", () => {
    expect(isDirectData({ status: "ok", data: [] })).toBe(true);
    expect(isDirectData({ data: [] })).toBeFalsy();
  });
});

describe("parseApiKeysList", () => {
  it("parses string body format", () => {
    const data = {
      body: JSON.stringify({ data: { apiKeys: [validApiKey] } }),
    };
    const result = parseApiKeysList(data);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe("key-1");
  });

  it("parses nested body.data format", () => {
    const data = { body: { data: { apiKeys: [validApiKey] } } };
    const result = parseApiKeysList(data);
    expect(result).toHaveLength(1);
  });

  it("parses direct data format", () => {
    const data = { status: "ok", data: { apiKeys: [validApiKey] } };
    const result = parseApiKeysList(data);
    expect(result).toHaveLength(1);
  });

  it("returns empty array for unexpected format", () => {
    expect(parseApiKeysList({ weird: true })).toEqual([]);
  });

  it("filters out invalid keys", () => {
    const data = {
      status: "ok",
      data: { apiKeys: [validApiKey, { bad: true }] },
    };
    const result = parseApiKeysList(data);
    expect(result).toHaveLength(1);
  });

  it("returns empty array on parse error", () => {
    const data = { body: "not-json{{{" };
    expect(parseApiKeysList(data)).toEqual([]);
  });
});

describe("parseApiKey", () => {
  it("parses string body format", () => {
    const data = { body: JSON.stringify({ data: validApiKey }) };
    expect(parseApiKey(data).id).toBe("key-1");
  });

  it("parses nested body.data format", () => {
    const data = { body: { data: validApiKey } };
    expect(parseApiKey(data).id).toBe("key-1");
  });

  it("parses direct data format", () => {
    const data = { status: "ok", data: validApiKey };
    expect(parseApiKey(data).id).toBe("key-1");
  });

  it("throws for invalid structure", () => {
    expect(() => parseApiKey({ weird: true })).toThrow("Failed to parse");
  });
});

describe("parseStringBodyResponse", () => {
  it("parses string body", () => {
    const data = { body: JSON.stringify({ result: "ok" }) };
    expect(parseStringBodyResponse<{ result: string }>(data)).toEqual({ result: "ok" });
  });

  it("returns direct data format", () => {
    const data = { status: "ok", data: { items: [] } };
    expect(parseStringBodyResponse(data)).toEqual(data);
  });

  it("returns raw data as fallback", () => {
    const data = { custom: true };
    expect(parseStringBodyResponse(data)).toEqual(data);
  });

  it("throws for falsy input", () => {
    expect(() => parseStringBodyResponse(null)).toThrow();
  });
});

describe("handleApiKeysError", () => {
  it("returns empty array for 403 errors", () => {
    const error = { response: { status: 403 } };
    expect(handleApiKeysError(error)).toEqual([]);
  });

  it("re-throws non-403 errors", () => {
    const error = { response: { status: 500 } };
    expect(() => handleApiKeysError(error)).toThrow();
  });
});

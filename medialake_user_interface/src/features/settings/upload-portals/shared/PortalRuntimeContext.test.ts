import { describe, expect, it } from "vitest";

import {
  CURRENT_PATH_KEY,
  DEFAULT_PORTAL_RUNTIME,
  RESERVED_SURVEY_KEYS,
  SELECTED_DESTINATION_KEY,
  collectMetadataValues,
} from "./PortalRuntimeContext";

/**
 * Unit tests for `collectMetadataValues` — the metadata contract helper.
 *
 * **Validates: Requirements 7.6** _(Design Property 9)_
 *
 * Property 9 (metadata contract): the `metadata` object the uploader question
 * passes to `getPresignedUrl` equals the collected metadata-field values with
 * the Reserved_Survey_Keys (`__selectedDestinationId`, `__currentPath`)
 * excluded. These tests pin that contract: reserved keys never leak, real
 * field values pass through (coerced to strings), and `null`/`undefined`
 * answers are dropped rather than surfacing as `"null"`/`"undefined"`.
 */
describe("collectMetadataValues — reserved-key contract (Req 7.6 / Property 9)", () => {
  it("returns metadata-field values and excludes both reserved keys", () => {
    const result = collectMetadataValues({
      data: {
        project_code: "X",
        region: "EU",
        [SELECTED_DESTINATION_KEY]: "d1",
        [CURRENT_PATH_KEY]: "/a/b",
      },
    });

    expect(result).toEqual({ project_code: "X", region: "EU" });
    expect(result).not.toHaveProperty(SELECTED_DESTINATION_KEY);
    expect(result).not.toHaveProperty(CURRENT_PATH_KEY);
  });

  it("excludes the literal reserved key names", () => {
    // Guards the contract against a future rename: the literal strings the
    // design reserves must be the ones filtered out. Includes the upload
    // hand-off keys the live uploader writes back for the survey-level submit.
    expect(RESERVED_SURVEY_KEYS).toEqual([
      "__selectedDestinationId",
      "__currentPath",
      "__uploadSessionId",
      "__uploadedFileCount",
      "__uploadInProgress",
    ]);
  });

  it("excludes reserved keys even when they carry non-string values", () => {
    const result = collectMetadataValues({
      data: {
        title: "Launch",
        [SELECTED_DESTINATION_KEY]: 123,
        [CURRENT_PATH_KEY]: { nested: true },
      },
    });

    expect(result).toEqual({ title: "Launch" });
  });

  it("skips null and undefined answers so they do not become 'null'/'undefined'", () => {
    const result = collectMetadataValues({
      data: {
        kept: "yes",
        skipped_null: null,
        skipped_undefined: undefined,
      },
    });

    expect(result).toEqual({ kept: "yes" });
    expect(result).not.toHaveProperty("skipped_null");
    expect(result).not.toHaveProperty("skipped_undefined");
  });

  it("coerces non-string field values to strings", () => {
    const result = collectMetadataValues({
      data: {
        count: 42,
        active: true,
        rate: 0,
      },
    });

    expect(result).toEqual({ count: "42", active: "true", rate: "0" });
  });

  it("returns an empty object when there are no metadata fields", () => {
    expect(
      collectMetadataValues({
        data: {
          [SELECTED_DESTINATION_KEY]: "d1",
          [CURRENT_PATH_KEY]: "/only/reserved",
        },
      })
    ).toEqual({});
  });

  it("tolerates a null/missing data object", () => {
    // SurveyJS always exposes a `data` object, but the helper guards against a
    // null answer object so it never throws on an empty/fresh survey.
    expect(collectMetadataValues({ data: null as unknown as Record<string, unknown> })).toEqual({});
  });

  it("does not mutate the input data object", () => {
    const data = {
      project_code: "X",
      [SELECTED_DESTINATION_KEY]: "d1",
    };
    const before = { ...data };
    collectMetadataValues({ data });
    expect(data).toEqual(before);
  });

  it("comma-joins multi-select array values (checkbox/tagbox)", () => {
    const result = collectMetadataValues({
      data: {
        tags: ["urgent", "review", "2024"],
        regions: ["NA", "EU"],
      },
    });

    expect(result).toEqual({ tags: "urgent, review, 2024", regions: "NA, EU" });
  });

  it("skips an empty array (a cleared multi-select) rather than emitting an empty value", () => {
    const result = collectMetadataValues({
      data: {
        kept: "yes",
        tags: [],
      },
    });

    expect(result).toEqual({ kept: "yes" });
    expect(result).not.toHaveProperty("tags");
  });

  it("drops null/undefined items inside a multi-select array", () => {
    const result = collectMetadataValues({
      data: {
        tags: ["a", null, undefined, "b"] as unknown[],
      },
    });

    expect(result).toEqual({ tags: "a, b" });
  });

  it("serializes boolean answers to 'true'/'false'", () => {
    const result = collectMetadataValues({
      data: {
        agreed: true,
        subscribed: false,
      },
    });

    expect(result).toEqual({ agreed: "true", subscribed: "false" });
  });

  it("JSON-stringifies plain object answers rather than '[object Object]'", () => {
    const result = collectMetadataValues({
      data: {
        nested: { a: 1, b: "x" },
      },
    });

    expect(result).toEqual({ nested: '{"a":1,"b":"x"}' });
  });
});

describe("DEFAULT_PORTAL_RUNTIME", () => {
  it("defaults to a non-interactive preview with no live session", () => {
    // A question rendered outside a provider must never attempt a live API
    // call; the default runtime is preview-mode with no session/config.
    expect(DEFAULT_PORTAL_RUNTIME.mode).toBe("preview");
    expect(DEFAULT_PORTAL_RUNTIME.sessionJwt).toBeNull();
    expect(DEFAULT_PORTAL_RUNTIME.config).toBeNull();
  });
});

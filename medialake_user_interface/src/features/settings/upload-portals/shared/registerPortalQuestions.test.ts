import { ElementFactory, Serializer } from "survey-core";
import { describe, expect, it } from "vitest";

import { PORTAL_QUESTION_TYPES, registerPortalQuestions } from "./registerPortalQuestions";

/**
 * Importing the module above already invokes `registerPortalQuestions()` once
 * at module-init (see the call at the bottom of the source file). These tests
 * therefore exercise the idempotency guard: every further call must be a no-op
 * that neither throws nor produces a duplicate registration.
 */

const ALL_TYPES = Object.values(PORTAL_QUESTION_TYPES);

/** Count how many times a type name appears in the global ElementFactory. */
const factoryCount = (type: string): number =>
  ElementFactory.Instance.getAllTypes().filter((t) => t === type).length;

describe("registerPortalQuestions — idempotency (Req 7.1, 7.2)", () => {
  it("registers all four custom question types", () => {
    for (const type of ALL_TYPES) {
      expect(Serializer.findClass(type)).toBeTruthy();
      expect(ElementFactory.Instance.getAllTypes()).toContain(type);
    }
  });

  it("does not throw when called repeatedly", () => {
    expect(() => {
      registerPortalQuestions();
      registerPortalQuestions();
      registerPortalQuestions();
    }).not.toThrow();
  });

  it("leaves exactly one registration per type after repeated calls", () => {
    registerPortalQuestions();
    registerPortalQuestions();

    for (const type of ALL_TYPES) {
      // ElementFactory lists each registered type exactly once.
      expect(factoryCount(type)).toBe(1);
      // Serializer resolves a single class for the type.
      expect(Serializer.findClass(type)).toBeTruthy();
    }
  });

  it("registers exactly the four expected type names", () => {
    expect(ALL_TYPES).toEqual([
      "portal-destination-selector",
      "portal-path-browser",
      "portal-path-builder",
      "portal-uppy-uploader",
    ]);
  });
});

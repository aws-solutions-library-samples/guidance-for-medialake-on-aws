import { describe, expect, it } from "vitest";
import { getPostLoginPath } from "./postLoginRedirect";

describe("getPostLoginPath", () => {
  it("returns pathname + search + hash of the original location", () => {
    expect(
      getPostLoginPath({ from: { pathname: "/videos/1", search: "?t=5", hash: "#notes" } })
    ).toBe("/videos/1?t=5#notes");
  });

  it("works when search and hash are absent", () => {
    expect(getPostLoginPath({ from: { pathname: "/collections" } })).toBe("/collections");
  });

  it.each([
    ["no state", undefined],
    ["null state", null],
    ["no from", {}],
    ["from is a string", { from: "/videos/1" }],
    ["non-string pathname", { from: { pathname: 42 } }],
    ["relative path", { from: { pathname: "videos/1" } }],
    ["protocol-relative //", { from: { pathname: "//evil.com" } }],
    ["protocol-relative with path", { from: { pathname: "//evil.com/videos/1" } }],
    ["backslash /\\", { from: { pathname: "/\\evil.com" } }],
    ["tab-smuggled //", { from: { pathname: "/\t/evil.com" } }],
    ["absolute URL", { from: { pathname: "https://evil.com/" } }],
    ["javascript: URL", { from: { pathname: "javascript:alert(1)" } }],
    ["sign-in page", { from: { pathname: "/sign-in" } }],
    ["sign-in sub-path", { from: { pathname: "/sign-in/x" } }],
  ])("falls back to / for %s", (_label, state) => {
    expect(getPostLoginPath(state)).toBe("/");
  });

  it("ignores non-string search/hash", () => {
    expect(getPostLoginPath({ from: { pathname: "/search", search: 1, hash: {} } })).toBe(
      "/search"
    );
  });
});

import { afterEach, describe, expect, it, vi } from "vitest";

// authService registers an Amplify Hub listener at import time; stub Amplify so
// importing it has no side effects.
vi.mock("aws-amplify/auth", () => ({
  fetchAuthSession: vi.fn(),
  getCurrentUser: vi.fn(),
  fetchUserAttributes: vi.fn(),
  signInWithRedirect: vi.fn(),
  signIn: vi.fn(),
}));
vi.mock("aws-amplify/utils", () => ({ Hub: { listen: vi.fn() } }));

import { resolvePostSignInReloadPath } from "./authService";

const goTo = (url: string, state: unknown = null) => {
  window.history.replaceState(state, "", url);
};

describe("resolvePostSignInReloadPath", () => {
  afterEach(() => goTo("/", null));

  it("returns the deep link stored in router state while still on /sign-in", () => {
    goTo("/sign-in", {
      usr: { from: { pathname: "/collections", search: "?view=grid", hash: "#top" } },
      key: "k",
      idx: 0,
    });
    expect(resolvePostSignInReloadPath()).toBe("/collections?view=grid#top");
  });

  it("falls back to / on /sign-in without a from location", () => {
    goTo("/sign-in", { usr: null, key: "k", idx: 0 });
    expect(resolvePostSignInReloadPath()).toBe("/");
  });

  it("falls back to / for an off-origin from location", () => {
    goTo("/sign-in", { usr: { from: { pathname: "//evil.com/x" } }, key: "k", idx: 0 });
    expect(resolvePostSignInReloadPath()).toBe("/");
  });

  it("reloads the current page when AuthPage already navigated away", () => {
    goTo("/videos/abc?t=5");
    expect(resolvePostSignInReloadPath()).toBe("/videos/abc?t=5");
  });

  it("returns / when the app is already on /", () => {
    goTo("/");
    expect(resolvePostSignInReloadPath()).toBe("/");
  });
});

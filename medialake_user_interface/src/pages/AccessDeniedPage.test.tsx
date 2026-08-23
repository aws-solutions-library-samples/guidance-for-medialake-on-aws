/**
 * Tests for AccessDeniedPage's navigation affordances.
 *
 * Regression cover for two ways off this page failing:
 *   - "Go Back" called navigate(-1) unconditionally. When /access-denied is the
 *     first entry in the session history — a deep link into a guarded route, a
 *     link opened from another app, a fresh tab, or a refresh while already here
 *     — that leaves MediaLake entirely instead of returning to it. Denials
 *     redirect with `replace`, so the denied route is overwritten rather than
 *     left behind, which makes index 0 a normal occurrence.
 *   - "Go to Home" pushed, leaving /access-denied one press of browser Back away.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const navigate = vi.fn();

vi.mock("react-router", () => ({
  useNavigate: () => navigate,
}));

import AccessDeniedPage from "./AccessDeniedPage";

/** Set React Router's session-history index, which lives on history.state.idx. */
const setHistoryIndex = (idx: unknown) => {
  window.history.replaceState(idx === undefined ? {} : { idx }, "", "/access-denied");
};

const clickButton = async (name: RegExp) => {
  await userEvent.click(screen.getByRole("button", { name }));
};

describe("AccessDeniedPage", () => {
  beforeEach(() => {
    navigate.mockClear();
    sessionStorage.clear();
  });

  it("renders the denial message", () => {
    setHistoryIndex(0);
    render(<AccessDeniedPage />);

    expect(screen.getByRole("heading", { name: /access denied/i })).toBeInTheDocument();
  });

  it("shows details supplied by the API interceptor and clears them", () => {
    setHistoryIndex(0);
    sessionStorage.setItem(
      "accessDeniedError",
      JSON.stringify({
        message: "You don't have permission to perform this action",
        requiredPermission: "assets:view",
      })
    );

    render(<AccessDeniedPage />);

    expect(screen.getByText(/don't have permission to perform this action/i)).toBeInTheDocument();
    expect(screen.getByText("assets:view")).toBeInTheDocument();
    expect(sessionStorage.getItem("accessDeniedError")).toBeNull();
  });

  describe("Go to Home", () => {
    it("replaces so this page leaves the history stack", async () => {
      setHistoryIndex(3);
      render(<AccessDeniedPage />);

      await clickButton(/go to home/i);

      expect(navigate).toHaveBeenCalledWith("/", { replace: true });
    });
  });

  describe("Go Back", () => {
    it("steps back when there is an in-app entry behind this one", async () => {
      setHistoryIndex(3);
      render(<AccessDeniedPage />);

      await clickButton(/go back/i);

      expect(navigate).toHaveBeenCalledWith(-1);
    });

    it("goes Home instead of leaving the app when this is the first entry", async () => {
      setHistoryIndex(0);
      render(<AccessDeniedPage />);

      await clickButton(/go back/i);

      expect(navigate).not.toHaveBeenCalledWith(-1);
      expect(navigate).toHaveBeenCalledWith("/", { replace: true });
    });

    it("falls back to Home when the history index is missing", async () => {
      setHistoryIndex(undefined);
      render(<AccessDeniedPage />);

      await clickButton(/go back/i);

      expect(navigate).not.toHaveBeenCalledWith(-1);
      expect(navigate).toHaveBeenCalledWith("/", { replace: true });
    });

    it("falls back to Home when the history index is not a number", async () => {
      setHistoryIndex("2");
      render(<AccessDeniedPage />);

      await clickButton(/go back/i);

      expect(navigate).not.toHaveBeenCalledWith(-1);
      expect(navigate).toHaveBeenCalledWith("/", { replace: true });
    });
  });
});

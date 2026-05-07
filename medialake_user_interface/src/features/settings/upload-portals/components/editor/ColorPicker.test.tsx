/**
 * Unit tests for ColorPicker.
 *
 * **Validates: Requirements 4.5, 4.6, 4.8, 17.1**
 *
 * Coverage:
 *   1. The swatch trigger renders with the accessible name
 *      `"Change {label} color, currently {value}"` (Requirement 16.4 /
 *      Acceptance 4.5 surface).
 *   2. Clicking the swatch opens the popover — evidenced by the hex
 *      TextField becoming present in the DOM (Requirement 4.5).
 *   3. Typing a valid hex and blurring keeps the value, while typing an
 *      invalid hex and blurring reverts to the last valid value
 *      (Requirement 4.8).
 *   4. The upstream `onChange` is debounced by 100ms after a color
 *      change — fake timers are used to assert nothing fires until the
 *      window elapses (Requirement 4.6).
 *   5. Click-away closes the popover (MUI Popover default backdrop).
 *   6. Pressing Escape closes the popover.
 *
 * Testing strategy note: driving `react-colorful`'s internal drag surface
 * from jsdom is fragile because it relies on pointer capture. Instead we
 * exercise the debounce and round-trip paths via the hex TextField we
 * own, which is the same surface a user hits when they type a color.
 */

import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import ColorPicker from "./ColorPicker";

describe("ColorPicker", () => {
  beforeEach(() => {
    // Each test owns its own timer / user-event instance.
    vi.useRealTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders the swatch trigger with the documented aria-label", () => {
    render(<ColorPicker label="Primary" value="#ff0000" onChange={() => {}} />);

    expect(
      screen.getByRole("button", {
        name: "Change Primary color, currently #ff0000",
      })
    ).toBeInTheDocument();
  });

  it("opens the popover when the swatch is clicked", async () => {
    const user = userEvent.setup();
    render(<ColorPicker label="Primary" value="#ff0000" onChange={() => {}} />);

    // Popover contents should be absent before opening.
    expect(screen.queryByRole("textbox", { name: "Hex color value" })).not.toBeInTheDocument();

    await user.click(
      screen.getByRole("button", {
        name: "Change Primary color, currently #ff0000",
      })
    );

    expect(await screen.findByRole("textbox", { name: "Hex color value" })).toBeInTheDocument();
  });

  it("keeps a valid hex typed into the input after blur", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();

    render(<ColorPicker label="Primary" value="#ff0000" onChange={onChange} />);

    await user.click(
      screen.getByRole("button", {
        name: "Change Primary color, currently #ff0000",
      })
    );

    const hexInput = await screen.findByRole("textbox", {
      name: "Hex color value",
    });

    await user.clear(hexInput);
    await user.type(hexInput, "#00ff00");
    // Tab out to trigger blur-based validation.
    await user.tab();

    // The visible input still shows the valid hex.
    expect(hexInput).toHaveValue("#00ff00");

    // Eventually the debounced onChange fires with the new color.
    await waitFor(() => {
      expect(onChange).toHaveBeenCalledWith("#00ff00");
    });
  });

  it("reverts an invalid hex entry to the last valid value on blur", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();

    render(<ColorPicker label="Primary" value="#ff0000" onChange={onChange} />);

    await user.click(
      screen.getByRole("button", {
        name: "Change Primary color, currently #ff0000",
      })
    );

    const hexInput = await screen.findByRole("textbox", {
      name: "Hex color value",
    });

    await user.clear(hexInput);
    await user.type(hexInput, "not-a-color");
    await user.tab();

    // The input snaps back to the last valid value — the initial `value`
    // prop — because nothing valid was committed in-between.
    expect(hexInput).toHaveValue("#ff0000");
    // And no upstream onChange was triggered by the invalid entry.
    expect(onChange).not.toHaveBeenCalled();
  });

  it("debounces upstream onChange by 100ms", async () => {
    const onChange = vi.fn();
    // Open the popover with real timers and userEvent. Once the hex input
    // is mounted we switch to fake timers to assert the debounce window.
    // Mixing `vi.useFakeTimers()` with `userEvent.setup()` is fragile
    // because MUI's Popover transitions schedule their own timers; doing
    // the open and the input edits via direct DOM events sidesteps that.
    const user = userEvent.setup();

    render(<ColorPicker label="Primary" value="#ff0000" onChange={onChange} />);

    await user.click(
      screen.getByRole("button", {
        name: "Change Primary color, currently #ff0000",
      })
    );

    const hexInput = await screen.findByRole<HTMLInputElement>("textbox", {
      name: "Hex color value",
    });

    // Now move to fake timers to control the 100ms debounce precisely.
    vi.useFakeTimers();

    // Typing directly via `fireEvent.change` writes the full value in one
    // synchronous update, matching what the component sees from a real
    // keystroke flush. A subsequent blur triggers validation + the
    // debounced upstream propagation.
    fireEvent.change(hexInput, { target: { value: "#112233" } });
    fireEvent.blur(hexInput);

    // Right after blur we have a pending timer but no upstream call.
    expect(onChange).not.toHaveBeenCalled();

    // Advance to just before the debounce window closes — still silent.
    act(() => {
      vi.advanceTimersByTime(99);
    });
    expect(onChange).not.toHaveBeenCalled();

    // Cross the 100ms threshold — now the debounced call fires exactly once.
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith("#112233");
  });

  it("closes the popover when clicking outside the dialog (backdrop)", async () => {
    const user = userEvent.setup();
    render(<ColorPicker label="Primary" value="#ff0000" onChange={() => {}} />);

    await user.click(
      screen.getByRole("button", {
        name: "Change Primary color, currently #ff0000",
      })
    );

    expect(await screen.findByRole("textbox", { name: "Hex color value" })).toBeInTheDocument();

    // MUI Popover renders an invisible backdrop with `aria-hidden="true"`
    // and the class `MuiBackdrop-invisible`. Clicking it dismisses the
    // popover — this exercises the same code path as a real click-away.
    const backdrop = document.querySelector(".MuiBackdrop-root");
    expect(backdrop).not.toBeNull();
    await user.click(backdrop as HTMLElement);

    await waitFor(() => {
      expect(screen.queryByRole("textbox", { name: "Hex color value" })).not.toBeInTheDocument();
    });
  });

  it("closes the popover on Escape and restores focus to the swatch trigger", async () => {
    const user = userEvent.setup();
    render(<ColorPicker label="Primary" value="#ff0000" onChange={() => {}} />);

    const trigger = screen.getByRole("button", {
      name: "Change Primary color, currently #ff0000",
    });
    await user.click(trigger);

    expect(await screen.findByRole("textbox", { name: "Hex color value" })).toBeInTheDocument();

    await user.keyboard("{Escape}");

    await waitFor(() => {
      expect(screen.queryByRole("textbox", { name: "Hex color value" })).not.toBeInTheDocument();
    });

    // MUI's Popover restores focus to the anchor element when closed,
    // which satisfies Requirement 16.11 / 4.9. Assert the swatch trigger
    // is the active element after Escape dismissal.
    await waitFor(() => {
      expect(document.activeElement).toBe(trigger);
    });
  });
});

/**
 * Unit tests for FontSelector.
 *
 * **Validates: Requirements 5.5, 5.7**
 *
 * Coverage:
 *   1. Renders a combobox with `aria-label="{label} font family"`
 *      (Requirement 16.6 surface + 5.5 combobox presence).
 *   2. Opening the combobox shows curated options including "Inter",
 *      "Roboto", and "JetBrains Mono" (Requirement 5.5 — curated list).
 *   3. Typing "jet" narrows the list to "JetBrains Mono" (Requirement
 *      5.5 — Autocomplete filters typed input).
 *   4. Selecting "Roboto" calls `onChange("Roboto")` AND
 *      `loadGoogleFont("Roboto")` on the same event (Requirement 5.7).
 *   5. An initial `value="Inter"` shows as the selected option.
 *   6. An initial `value="Custom Family"` that is NOT in the curated
 *      list still renders as the selected option via the synthesized
 *      fallback entry.
 *
 * The Google Fonts loader is mocked module-wide so the tests never
 * touch `document.head` via a real stylesheet injection path; we simply
 * assert that `loadGoogleFont` is invoked with the expected family.
 */

import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import FontSelector from "./FontSelector";
import { loadGoogleFont } from "../../utils/loadGoogleFont";

vi.mock("../../utils/loadGoogleFont", () => ({
  loadGoogleFont: vi.fn(),
  buildGoogleFontHref: vi.fn(),
  isSystemFontStack: vi.fn(),
  GOOGLE_FONT_LINK_ID_PREFIX: "google-font-",
}));

describe("FontSelector", () => {
  beforeEach(() => {
    vi.mocked(loadGoogleFont).mockClear();
  });

  it("renders a combobox with the `{label} font family` aria-label", () => {
    render(<FontSelector label="Body" value="Inter" onChange={() => {}} />);

    expect(screen.getByRole("combobox", { name: "Body font family" })).toBeInTheDocument();
  });

  it("opens the listbox with curated options on click", async () => {
    const user = userEvent.setup();
    render(<FontSelector label="Body" value="Inter" onChange={() => {}} />);

    const input = screen.getByRole("combobox", { name: "Body font family" });
    await user.click(input);

    const listbox = await screen.findByRole("listbox");
    // Curated list surface check: three spec-mandated entries must appear.
    expect(within(listbox).getByRole("option", { name: "Inter" })).toBeInTheDocument();
    expect(within(listbox).getByRole("option", { name: "Roboto" })).toBeInTheDocument();
    expect(within(listbox).getByRole("option", { name: "JetBrains Mono" })).toBeInTheDocument();
  });

  it("filters options to match typed input", async () => {
    const user = userEvent.setup();
    render(<FontSelector label="Body" value="Inter" onChange={() => {}} />);

    const input = screen.getByRole("combobox", { name: "Body font family" });
    // Clear the initial `value` ("Inter") so the filter buffer is empty
    // before we type our narrowing query. Without this, `user.type`
    // appends to the displayed selection and we end up filtering on
    // `"Interjet"`, which matches nothing.
    await user.click(input);
    await user.clear(input);
    await user.type(input, "jet");

    const listbox = await screen.findByRole("listbox");
    const options = within(listbox).getAllByRole("option");

    // Exactly one match — MUI's default filter is substring + case-insensitive.
    expect(options).toHaveLength(1);
    expect(options[0]).toHaveTextContent("JetBrains Mono");
  });

  it("fires onChange and loadGoogleFont when an option is selected", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();

    render(<FontSelector label="Body" value="Inter" onChange={onChange} />);

    const input = screen.getByRole("combobox", { name: "Body font family" });
    await user.click(input);

    const listbox = await screen.findByRole("listbox");
    await user.click(within(listbox).getByRole("option", { name: "Roboto" }));

    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith("Roboto");
    expect(loadGoogleFont).toHaveBeenCalledTimes(1);
    expect(loadGoogleFont).toHaveBeenCalledWith("Roboto");
  });

  it("renders a curated `value` (Inter) as the current selection", () => {
    render(<FontSelector label="Body" value="Inter" onChange={() => {}} />);

    const input = screen.getByRole<HTMLInputElement>("combobox", {
      name: "Body font family",
    });
    expect(input.value).toBe("Inter");
  });

  it("falls back to a synthesized option when `value` is not curated", () => {
    render(<FontSelector label="Body" value="Custom Family" onChange={() => {}} />);

    const input = screen.getByRole<HTMLInputElement>("combobox", {
      name: "Body font family",
    });
    expect(input.value).toBe("Custom Family");
  });
});

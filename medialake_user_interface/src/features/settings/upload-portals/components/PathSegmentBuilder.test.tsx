import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeProvider, createTheme } from "@mui/material";
import PathSegmentBuilder, { generateRegexFromType, getExampleValue } from "./PathSegmentBuilder";
import type { PathSegmentRuleExtended } from "@/features/portal/types/portal.types";

const theme = createTheme();

function renderWithTheme(ui: React.ReactElement) {
  return render(<ThemeProvider theme={theme}>{ui}</ThemeProvider>);
}

/* ------------------------------------------------------------------ */
/*  generateRegexFromType                                             */
/* ------------------------------------------------------------------ */

describe("generateRegexFromType", () => {
  it('returns "^.+$" for text', () => {
    expect(generateRegexFromType("text")).toBe("^.+$");
  });

  it('returns "^[a-zA-Z0-9]+$" for alphanumeric', () => {
    expect(generateRegexFromType("alphanumeric")).toBe("^[a-zA-Z0-9]+$");
  });

  it('returns "^\\d+$" for numbers', () => {
    expect(generateRegexFromType("numbers")).toBe("^\\d+$");
  });

  it('returns "^\\d{4}-\\d{2}-\\d{2}$" for date', () => {
    expect(generateRegexFromType("date")).toBe("^\\d{4}-\\d{2}-\\d{2}$");
  });

  it("returns an alternation regex for list with values", () => {
    expect(generateRegexFromType("list", ["Marketing", "Sales"])).toBe("^(Marketing|Sales)$");
  });

  it("escapes special regex characters in list values", () => {
    const result = generateRegexFromType("list", ["a.b", "c+d"]);
    expect(result).toBe("^(a\\.b|c\\+d)$");
  });

  it('returns "^.+$" for list with no values', () => {
    expect(generateRegexFromType("list", [])).toBe("^.+$");
    expect(generateRegexFromType("list")).toBe("^.+$");
  });

  it('returns "" for pattern (admin provides their own)', () => {
    expect(generateRegexFromType("pattern")).toBe("");
  });
});

/* ------------------------------------------------------------------ */
/*  getExampleValue                                                   */
/* ------------------------------------------------------------------ */

describe("getExampleValue", () => {
  it('returns "example" for text', () => {
    expect(getExampleValue("text")).toBe("example");
  });

  it('returns "ABC123" for alphanumeric', () => {
    expect(getExampleValue("alphanumeric")).toBe("ABC123");
  });

  it('returns "42" for numbers', () => {
    expect(getExampleValue("numbers")).toBe("42");
  });

  it('returns "2024-01-15" for date', () => {
    expect(getExampleValue("date")).toBe("2024-01-15");
  });

  it("returns the first list value for list", () => {
    expect(getExampleValue("list", ["Marketing", "Sales"])).toBe("Marketing");
  });

  it('returns "option1" for list with no values', () => {
    expect(getExampleValue("list")).toBe("option1");
  });

  it('returns "value" for pattern', () => {
    expect(getExampleValue("pattern")).toBe("value");
  });
});

/* ------------------------------------------------------------------ */
/*  PathSegmentBuilder component                                      */
/* ------------------------------------------------------------------ */

describe("PathSegmentBuilder", () => {
  const defaultSegments: PathSegmentRuleExtended[] = [
    {
      id: "test-seg-1",
      label: "Department",
      position: 0,
      regex: "^.+$",
      segmentType: "text",
    },
    {
      id: "test-seg-2",
      label: "Project",
      position: 1,
      regex: "^[a-zA-Z0-9]+$",
      segmentType: "alphanumeric",
    },
  ];

  it("renders segment cards for each segment", () => {
    const onChange = vi.fn();
    renderWithTheme(<PathSegmentBuilder segments={defaultSegments} onChange={onChange} />);

    // Both labels should be visible as input values
    const inputs = screen.getAllByRole("textbox");
    const labelInputs = inputs.filter(
      (input) =>
        (input as HTMLInputElement).value === "Department" ||
        (input as HTMLInputElement).value === "Project"
    );
    expect(labelInputs).toHaveLength(2);
  });

  it("renders the Add segment button", () => {
    const onChange = vi.fn();
    renderWithTheme(<PathSegmentBuilder segments={[]} onChange={onChange} />);

    expect(screen.getByText("Add segment")).toBeInTheDocument();
  });

  it("calls onChange with a new segment when Add segment is clicked", async () => {
    const onChange = vi.fn();
    renderWithTheme(<PathSegmentBuilder segments={[]} onChange={onChange} />);

    await userEvent.click(screen.getByText("Add segment"));

    expect(onChange).toHaveBeenCalledTimes(1);
    const newSegments = onChange.mock.calls[0][0];
    expect(newSegments).toHaveLength(1);
    expect(newSegments[0].segmentType).toBe("text");
    expect(newSegments[0].regex).toBe("^.+$");
  });

  it("removes a segment when delete is clicked", async () => {
    const onChange = vi.fn();
    renderWithTheme(<PathSegmentBuilder segments={defaultSegments} onChange={onChange} />);

    const deleteButtons = screen.getAllByLabelText("Remove segment");
    await userEvent.click(deleteButtons[0]);

    expect(onChange).toHaveBeenCalledTimes(1);
    const updated = onChange.mock.calls[0][0];
    expect(updated).toHaveLength(1);
    expect(updated[0].label).toBe("Project");
  });

  it("reorders segments via move up/down buttons", async () => {
    const onChange = vi.fn();
    renderWithTheme(<PathSegmentBuilder segments={defaultSegments} onChange={onChange} />);

    // Move second segment up
    const moveUpButtons = screen.getAllByLabelText("Move segment up");
    // The second segment's move-up button is the second one
    await userEvent.click(moveUpButtons[1]);

    expect(onChange).toHaveBeenCalledTimes(1);
    const reordered = onChange.mock.calls[0][0];
    expect(reordered[0].label).toBe("Project");
    expect(reordered[1].label).toBe("Department");
  });

  it("disables move up on first segment and move down on last", () => {
    const onChange = vi.fn();
    renderWithTheme(<PathSegmentBuilder segments={defaultSegments} onChange={onChange} />);

    const moveUpButtons = screen.getAllByLabelText("Move segment up");
    const moveDownButtons = screen.getAllByLabelText("Move segment down");

    // First segment's move-up should be disabled
    expect(moveUpButtons[0].closest("button")).toBeDisabled();
    // Last segment's move-down should be disabled
    expect(moveDownButtons[moveDownButtons.length - 1].closest("button")).toBeDisabled();
  });

  it("shows the live path preview with example values", () => {
    const onChange = vi.fn();
    renderWithTheme(<PathSegmentBuilder segments={defaultSegments} onChange={onChange} />);

    // Preview should show label placeholders and example values
    expect(screen.getByText("Path preview")).toBeInTheDocument();
    expect(screen.getByText("{Department}/{Project}")).toBeInTheDocument();
    expect(screen.getByText(/Example:.*example\/ABC123/)).toBeInTheDocument();
  });

  it("renders separator toggle when onSeparatorChange is provided", () => {
    const onChange = vi.fn();
    const onSepChange = vi.fn();
    renderWithTheme(
      <PathSegmentBuilder
        segments={defaultSegments}
        onChange={onChange}
        separator="/"
        onSeparatorChange={onSepChange}
      />
    );

    expect(screen.getByText("Separator:")).toBeInTheDocument();
    // All four separator options should be present
    expect(screen.getByLabelText("Separator /")).toBeInTheDocument();
    expect(screen.getByLabelText("Separator -")).toBeInTheDocument();
    expect(screen.getByLabelText("Separator _")).toBeInTheDocument();
    expect(screen.getByLabelText("Separator .")).toBeInTheDocument();
  });

  it("calls onSeparatorChange when a separator is selected", async () => {
    const onChange = vi.fn();
    const onSepChange = vi.fn();
    renderWithTheme(
      <PathSegmentBuilder
        segments={defaultSegments}
        onChange={onChange}
        separator="/"
        onSeparatorChange={onSepChange}
      />
    );

    await userEvent.click(screen.getByLabelText("Separator -"));
    expect(onSepChange).toHaveBeenCalledWith("-");
  });

  it("shows chip preview for list type segments", async () => {
    const listSegment: PathSegmentRuleExtended[] = [
      {
        id: "test-list-1",
        label: "Team",
        position: 0,
        regex: "^(Marketing|Sales)$",
        segmentType: "list",
        listValues: ["Marketing", "Sales"],
      },
    ];
    const onChange = vi.fn();
    renderWithTheme(<PathSegmentBuilder segments={listSegment} onChange={onChange} />);

    // Chips should be visible
    expect(screen.getByText("Marketing")).toBeInTheDocument();
    expect(screen.getByText("Sales")).toBeInTheDocument();
  });

  it("shows regex input for pattern type segments", () => {
    const patternSegment: PathSegmentRuleExtended[] = [
      {
        id: "test-pattern-1",
        label: "Code",
        position: 0,
        regex: "^[A-Z]{3}$",
        segmentType: "pattern",
      },
    ];
    const onChange = vi.fn();
    renderWithTheme(<PathSegmentBuilder segments={patternSegment} onChange={onChange} />);

    // Should show the regex input with the pattern value
    const regexInput = screen.getByDisplayValue("^[A-Z]{3}$");
    expect(regexInput).toBeInTheDocument();
  });
});

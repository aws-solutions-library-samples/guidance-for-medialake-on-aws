import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { KeyValueEditor } from "./KeyValueEditor";

describe("KeyValueEditor", () => {
  it("renders rows from the rows prop", () => {
    const rows = [
      { key: "project", value: "alpha" },
      { key: "region", value: "us-west-2" },
    ];
    render(<KeyValueEditor rows={rows} onChange={() => {}} />);

    const keyInputs = screen.getAllByPlaceholderText("Key");
    const valueInputs = screen.getAllByPlaceholderText("Value");

    expect(keyInputs).toHaveLength(2);
    expect(valueInputs).toHaveLength(2);
    expect(keyInputs[0]).toHaveValue("project");
    expect(valueInputs[0]).toHaveValue("alpha");
    expect(keyInputs[1]).toHaveValue("region");
    expect(valueInputs[1]).toHaveValue("us-west-2");
  });

  it("renders empty state with no rows", () => {
    render(<KeyValueEditor rows={[]} onChange={() => {}} />);

    expect(screen.queryAllByPlaceholderText("Key")).toHaveLength(0);
    expect(screen.getByText("Add Row")).toBeInTheDocument();
  });

  it("calls onChange with a new empty row when Add Row is clicked", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const rows = [{ key: "a", value: "b" }];

    render(<KeyValueEditor rows={rows} onChange={onChange} />);
    await user.click(screen.getByText("Add Row"));

    expect(onChange).toHaveBeenCalledWith([
      { key: "a", value: "b" },
      { key: "", value: "" },
    ]);
  });

  it("calls onChange without the removed row when remove is clicked", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const rows = [
      { key: "a", value: "1" },
      { key: "b", value: "2" },
    ];

    render(<KeyValueEditor rows={rows} onChange={onChange} />);
    const removeButtons = screen.getAllByLabelText(/Remove metadata row/);
    await user.click(removeButtons[0]);

    expect(onChange).toHaveBeenCalledWith([{ key: "b", value: "2" }]);
  });

  it("calls onChange with updated key when a key field changes", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const rows = [{ key: "", value: "" }];

    render(<KeyValueEditor rows={rows} onChange={onChange} />);
    const keyInput = screen.getByPlaceholderText("Key");
    await user.type(keyInput, "x");

    expect(onChange).toHaveBeenCalledWith([{ key: "x", value: "" }]);
  });

  it("calls onChange with updated value when a value field changes", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const rows = [{ key: "k", value: "" }];

    render(<KeyValueEditor rows={rows} onChange={onChange} />);
    const valueInput = screen.getByPlaceholderText("Value");
    await user.type(valueInput, "v");

    expect(onChange).toHaveBeenCalledWith([{ key: "k", value: "v" }]);
  });

  it("renders the label when provided", () => {
    render(<KeyValueEditor rows={[]} onChange={() => {}} label="Custom Metadata" />);
    expect(screen.getByText("Custom Metadata")).toBeInTheDocument();
  });

  it("does not render a label when not provided", () => {
    render(<KeyValueEditor rows={[]} onChange={() => {}} />);
    expect(screen.queryByText("Custom Metadata")).not.toBeInTheDocument();
  });
});

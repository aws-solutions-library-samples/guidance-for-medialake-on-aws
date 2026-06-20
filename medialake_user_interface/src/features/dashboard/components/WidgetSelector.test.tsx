import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { WIDGET_DEFINITIONS } from "../store/dashboardStore";
import { WidgetSelector } from "./WidgetSelector";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (_key: string, fallback?: string) => fallback || _key }),
}));

describe("WidgetSelector", () => {
  it("renders My Assets item from availableWidgets and fires onAddWidget", async () => {
    const onAddWidget = vi.fn();
    const availableWidgets = [WIDGET_DEFINITIONS["my-assets"]];

    render(
      <WidgetSelector
        isOpen={true}
        onClose={vi.fn()}
        availableWidgets={availableWidgets}
        onAddWidget={onAddWidget}
      />
    );

    expect(screen.getByText("My Assets")).toBeInTheDocument();

    await userEvent.click(screen.getByText("My Assets"));
    expect(onAddWidget).toHaveBeenCalledWith("my-assets");
  });
});

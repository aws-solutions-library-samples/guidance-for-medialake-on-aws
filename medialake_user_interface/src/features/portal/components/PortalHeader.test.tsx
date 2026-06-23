import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ThemeProvider, createTheme } from "@mui/material/styles";

import PortalHeader from "./PortalHeader";

const theme = createTheme({});

const renderHeader = (props: React.ComponentProps<typeof PortalHeader>) =>
  render(
    <ThemeProvider theme={theme}>
      <PortalHeader {...props} />
    </ThemeProvider>
  );

/**
 * Verifies the title fallback contract: the portal `name` is shown unless a
 * meaningful `titleHtml` is provided. Visually-empty Tiptap markup (a cleared
 * title leaves `<p></p>`) must NOT count as content — otherwise the header
 * renders blank instead of falling back to `name`.
 */
describe("PortalHeader title fallback", () => {
  it("renders the plain-text name when no titleHtml is provided", () => {
    renderHeader({ name: "My Portal" });
    expect(screen.getByRole("heading", { name: "My Portal" })).toBeInTheDocument();
  });

  it("renders titleHtml when it carries real content", () => {
    renderHeader({ name: "My Portal", titleHtml: "<h1>Welcome Uploaders</h1>" });
    expect(screen.getByText("Welcome Uploaders")).toBeInTheDocument();
    expect(screen.queryByText("My Portal")).not.toBeInTheDocument();
  });

  it("falls back to name when titleHtml is an empty paragraph", () => {
    renderHeader({ name: "My Portal", titleHtml: "<p></p>" });
    expect(screen.getByRole("heading", { name: "My Portal" })).toBeInTheDocument();
  });

  it("falls back to name when titleHtml is a paragraph with only a line break", () => {
    renderHeader({ name: "My Portal", titleHtml: "<p><br></p>" });
    expect(screen.getByRole("heading", { name: "My Portal" })).toBeInTheDocument();
  });

  it("falls back to name when titleHtml is whitespace/nbsp only", () => {
    renderHeader({ name: "My Portal", titleHtml: "<p>&nbsp; </p>" });
    expect(screen.getByRole("heading", { name: "My Portal" })).toBeInTheDocument();
  });
});
